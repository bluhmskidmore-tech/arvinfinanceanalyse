from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from backend.app.core_finance.hybrid_fusion_config import (
    HybridFusionThresholds,
    load_hybrid_fusion_thresholds,
)

FORMULA_VERSION = "rv_hybrid_fusion_candidates_v3"
ACTIVE_MARKET_STATES = {"WARM", "HOT"}
MAX_CANDIDATES = 10


@dataclass(frozen=True)
class HybridFusionResult:
    payload: dict[str, object]


def compute_hybrid_fusion_candidates(
    *,
    as_of_date: str,
    market_state: str,
    sector_rank_payload: dict[str, object] | None,
    stock_candidates_payload: dict[str, object] | None,
    factor_screen_payload: dict[str, object] | None,
    theme_breakout_payload: dict[str, object] | None,
    macro_score: float | None = None,
    thresholds: HybridFusionThresholds | None = None,
) -> HybridFusionResult:
    resolved_thresholds = thresholds or load_hybrid_fusion_thresholds()
    if market_state not in ACTIVE_MARKET_STATES:
        return HybridFusionResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                items=[],
                coverage_note=f"Hybrid fusion inactive for market_state {market_state}; active states are WARM/HOT.",
            )
        )

    sector_ranks = _sector_ranks(sector_rank_payload)
    stock_rows = _rows_by_code(_payload_items(stock_candidates_payload))
    factor_rows = _rows_by_code(_payload_items(factor_screen_payload))
    theme_rows = _theme_stock_rows(theme_breakout_payload)
    stock_codes = sorted(set(stock_rows) | set(factor_rows) | set(theme_rows))
    if not stock_codes:
        return HybridFusionResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                items=[],
                coverage_note="No usable hybrid fusion candidate sources.",
            )
        )

    factor_rank_count = max(1, len(factor_rows))
    movement_event_counts = _movement_event_counts(theme_rows)
    scored: list[dict[str, object]] = []
    for stock_code in stock_codes:
        sources = _source_rows(
            stock_code=stock_code,
            stock_rows=stock_rows,
            factor_rows=factor_rows,
            theme_rows=theme_rows,
        )
        base = _first_row(sources)
        stock_name = _first_text(*(row.get("stock_name") for row in sources)) or stock_code
        sector_code = _first_text(*(row.get("sector_code") for row in sources))
        sector_name = _first_text(*(row.get("sector_name") for row in sources))
        sector_rank = _first_int(
            stock_rows.get(stock_code, {}).get("sector_rank"),
            theme_rows.get(stock_code, {}).get("sector_rank"),
            sector_ranks.get(sector_code),
        )
        sector_score = _sector_score(sector_rank)
        factor_rank_score = _factor_rank_score(factor_rows.get(stock_code), factor_rank_count)
        source_kinds = _source_kinds(stock_code, stock_rows=stock_rows, factor_rows=factor_rows, theme_rows=theme_rows)
        theme_row = theme_rows.get(stock_code)
        stock_row = stock_rows.get(stock_code)
        price_confirm_score = _price_confirm_score(stock_row=stock_row, theme_row=theme_row)
        cycle_score = _cycle_score(
            macro_score=macro_score,
            sector_score=sector_score,
            market_flow_score=price_confirm_score,
            factor_rank_score=factor_rank_score,
            thresholds=resolved_thresholds,
        )
        crowding_score = _crowding_score(stock_row=stock_row, theme_row=theme_row)
        crowding_penalty = _crowding_penalty(stock_row=stock_row, theme_row=theme_row)
        vcov_score = _vcov_score(theme_row)
        consensus_score = _consensus_score(source_kinds)
        burst_score = _burst_score(theme_row, movement_event_counts=movement_event_counts)
        hygiene_score = _hygiene_score(stock_row=stock_row, theme_row=theme_row, sector_rank=sector_rank)
        regime_score = _clamp(cycle_score)
        lifecourt_proxy_score = _lifecourt_proxy_score(
            vcov_score=vcov_score,
            consensus_score=consensus_score,
            burst_score=burst_score,
            price_confirm_score=price_confirm_score,
            crowding_score=crowding_score,
            hygiene_score=hygiene_score,
            regime_score=regime_score,
        )
        fusion_score = round(
            resolved_thresholds.fusion_cycle_weight * cycle_score
            + resolved_thresholds.fusion_life_weight * lifecourt_proxy_score,
            6,
        )
        attention_score = vcov_score
        scored.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "sector_code": sector_code,
                "sector_name": sector_name,
                "fusion_score": fusion_score,
                "cycle_score": round(cycle_score, 6),
                "lifecourt_proxy_score": round(lifecourt_proxy_score, 6),
                "attention_score": round(attention_score, 6),
                "price_confirm_score": round(price_confirm_score, 6),
                "crowding_penalty": round(crowding_penalty, 6),
                "crowding_score": round(crowding_score, 6),
                "vcov_score": round(vcov_score, 6),
                "consensus_score": round(consensus_score, 6),
                "burst_score": round(burst_score, 6),
                "hygiene_score": round(hygiene_score, 6),
                "regime_score": round(regime_score, 6),
                "confidence": _confidence(source_kinds),
                "reason": _reason(
                    cycle_score=cycle_score,
                    lifecourt_proxy_score=lifecourt_proxy_score,
                    source_kinds=source_kinds,
                ),
                "evidence": {
                    "signal_kind": "hybrid_fusion",
                    "market_state": market_state,
                    "source_kinds": source_kinds,
                    "sector_rank": sector_rank,
                    "sector_score": round(sector_score, 6),
                    "factor_rank_score": round(factor_rank_score, 6),
                    "formula_version": FORMULA_VERSION,
                    "lifecourt_formula": (
                        "0.18*VCOV + 0.14*CONS + 0.14*BURST + 0.20*PCONF "
                        "- 0.16*CROWD + 0.10*HYGIENE + 0.08*REGIME"
                    ),
                    "fusion_weights": {
                        "cycle": resolved_thresholds.fusion_cycle_weight,
                        "lifecourt": resolved_thresholds.fusion_life_weight,
                    },
                    "macro_score": macro_score,
                    "cycle_formula": (
                        "0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 Valuation"
                        if macro_score is not None
                        else "0.70 Industry + 0.30 Valuation (macro pending)"
                    ),
                },
            }
        )

    life_long_thresholds = _life_long_thresholds(scored, thresholds=resolved_thresholds)
    stance_thresholds = _stance_thresholds(scored, thresholds=resolved_thresholds)
    for row in scored:
        row["life_long_pass"] = _life_long_pass(row, thresholds=life_long_thresholds)
        row["fusion_action"] = _fusion_action(
            cycle_score=cast(float, row["cycle_score"]),
            lifecourt_proxy_score=cast(float, row["lifecourt_proxy_score"]),
            stance_thresholds=stance_thresholds,
        )
        row["reason"] = _reason(
            cycle_score=cast(float, row["cycle_score"]),
            lifecourt_proxy_score=cast(float, row["lifecourt_proxy_score"]),
            source_kinds=cast(list[str], row["evidence"]["source_kinds"]),
            life_long_pass=cast(bool, row["life_long_pass"]),
            fusion_action=str(row["fusion_action"]),
        )

    ordered = sorted(
        scored,
        key=lambda row: (
            -int(cast(bool, row["life_long_pass"])),
            -cast(float, row["fusion_score"]),
            -cast(float, row["cycle_score"]),
            -cast(float, row["lifecourt_proxy_score"]),
            str(row["stock_code"]),
        ),
    )[:MAX_CANDIDATES]
    ranked = [{"rank": index, **row} for index, row in enumerate(ordered, start=1)]
    return HybridFusionResult(
        payload=_build_payload(
            as_of_date=as_of_date,
            market_state=market_state,
            items=ranked,
            macro_score=macro_score,
            coverage_note=_coverage_note(macro_score=macro_score),
        )
    )


def _coverage_note(*, macro_score: float | None) -> str:
    base = (
        "Hybrid fusion uses cycle rotation + lifecourt proxy reconstruction "
        "(VCOV/CONS/BURST/PCONF/CROWD/HYGIENE/REGIME); observation-only."
    )
    if macro_score is None:
        return f"{base} Macro layer pending PMI/credit_impulse/price_spread."
    return f"{base} Macro layer landed (MacroScore={macro_score:.3f})."


def _cycle_score(
    *,
    macro_score: float | None,
    sector_score: float,
    market_flow_score: float,
    factor_rank_score: float,
    thresholds: HybridFusionThresholds,
) -> float:
    if macro_score is None:
        return _clamp(
            thresholds.legacy_cycle_sector_weight * sector_score
            + thresholds.legacy_cycle_factor_weight * factor_rank_score
        )
    return _clamp(
        thresholds.cycle_macro_weight * macro_score
        + thresholds.cycle_industry_weight * sector_score
        + thresholds.cycle_market_flow_weight * market_flow_score
        + thresholds.cycle_valuation_weight * factor_rank_score
    )


def _build_payload(
    *,
    as_of_date: str,
    market_state: str,
    items: list[dict[str, object]],
    coverage_note: str,
    macro_score: float | None = None,
) -> dict[str, object]:
    return {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "observation_only": True,
        "macro_score": macro_score,
        "candidate_count": len(items),
        "coverage_note": coverage_note,
        "items": items,
    }


def _payload_items(payload: dict[str, object] | None) -> list[dict[str, object]]:
    raw = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return []
    return [cast(dict[str, object], item) for item in raw if isinstance(item, dict) and _text(item.get("stock_code"))]


def _rows_by_code(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for row in rows:
        code = _text(row.get("stock_code"))
        if code and code not in out:
            out[code] = row
    return out


def _theme_stock_rows(payload: dict[str, object] | None) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    themes = _payload_items_without_stock_code(payload)
    for theme in themes:
        raw_items = theme.get("items")
        if not isinstance(raw_items, list):
            continue
        theme_rank = _safe_int(theme.get("rank"))
        movement_event_count = _safe_int(theme.get("movement_event_count")) or 0
        for index, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                continue
            row = dict(cast(dict[str, object], raw))
            code = _text(row.get("stock_code"))
            if not code:
                continue
            row["theme_rank"] = theme_rank
            row["theme_key"] = theme.get("theme_key")
            row["theme_name"] = theme.get("theme_name")
            row["stock_rank_in_theme"] = index
            row["theme_movement_event_count"] = movement_event_count
            out.setdefault(code, row)
    return out


def _payload_items_without_stock_code(payload: dict[str, object] | None) -> list[dict[str, object]]:
    raw = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return []
    return [cast(dict[str, object], item) for item in raw if isinstance(item, dict)]


def _sector_ranks(payload: dict[str, object] | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in _payload_items_without_stock_code(payload):
        sector_code = _text(row.get("sector_code"))
        rank = _safe_int(row.get("rank"))
        if sector_code and rank is not None:
            out[sector_code] = rank
    return out


def _source_rows(
    *,
    stock_code: str,
    stock_rows: dict[str, dict[str, object]],
    factor_rows: dict[str, dict[str, object]],
    theme_rows: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    return [row for row in (stock_rows.get(stock_code), factor_rows.get(stock_code), theme_rows.get(stock_code)) if row]


def _first_row(rows: list[dict[str, object]]) -> dict[str, object]:
    return rows[0] if rows else {}


def _source_kinds(
    stock_code: str,
    *,
    stock_rows: dict[str, dict[str, object]],
    factor_rows: dict[str, dict[str, object]],
    theme_rows: dict[str, dict[str, object]],
) -> list[str]:
    kinds: list[str] = []
    if stock_code in stock_rows:
        kinds.append("stock_candidate")
    if stock_code in factor_rows:
        kinds.append("factor_screen")
    if stock_code in theme_rows:
        kinds.append("theme_breakout")
    return kinds


def _sector_score(rank: int | None) -> float:
    if rank == 1:
        return 1.0
    if rank == 2:
        return 0.667
    if rank == 3:
        return 0.333
    return 0.0


def _factor_rank_score(row: dict[str, object] | None, rank_count: int) -> float:
    rank = _safe_int(row.get("rank") if row else None)
    if rank is None or rank_count <= 1:
        return 1.0 if rank == 1 else 0.0
    return _clamp((rank_count - rank) / (rank_count - 1))


def _attention_score(row: dict[str, object] | None) -> float:
    return _vcov_score(row)


def _vcov_score(row: dict[str, object] | None) -> float:
    if not row:
        return 0.0
    theme_rank = _safe_int(row.get("theme_rank")) or 99
    rank_component = _clamp((11 - min(theme_rank, 10)) / 10)
    event_count = (_safe_int(row.get("movement_event_count")) or 0) + (
        _safe_int(row.get("theme_movement_event_count")) or 0
    )
    event_component = _clamp(event_count / 5)
    strong_component = 0.25 if bool(row.get("closed_up_limit")) or (_safe_float(row.get("pctchange")) or 0) >= 5 else 0
    return _clamp(0.55 * rank_component + 0.3 * event_component + strong_component)


def _consensus_score(source_kinds: list[str]) -> float:
    if len(source_kinds) >= 3:
        return 1.0
    if len(source_kinds) == 2:
        return 0.667
    if len(source_kinds) == 1:
        return 0.333
    return 0.0


def _movement_event_counts(theme_rows: dict[str, dict[str, object]]) -> list[int]:
    counts: list[int] = []
    for row in theme_rows.values():
        event_count = (_safe_int(row.get("movement_event_count")) or 0) + (
            _safe_int(row.get("theme_movement_event_count")) or 0
        )
        counts.append(event_count)
    return counts


def _burst_score(row: dict[str, object] | None, *, movement_event_counts: list[int]) -> float:
    if not row:
        return 0.0
    event_count = (_safe_int(row.get("movement_event_count")) or 0) + (
        _safe_int(row.get("theme_movement_event_count")) or 0
    )
    if not movement_event_counts:
        return _clamp(event_count / 5)
    median = sorted(movement_event_counts)[len(movement_event_counts) // 2]
    if median <= 0:
        return _clamp(event_count / 5)
    return _clamp((event_count - median) / max(median, 1))


def _crowding_score(
    *,
    stock_row: dict[str, object] | None,
    theme_row: dict[str, object] | None,
) -> float:
    return _crowding_penalty(stock_row=stock_row, theme_row=theme_row)


def _hygiene_score(
    *,
    stock_row: dict[str, object] | None,
    theme_row: dict[str, object] | None,
    sector_rank: int | None,
) -> float:
    score = 1.0
    if sector_rank is not None and sector_rank > 3:
        score -= 0.25
    if bool((stock_row or {}).get("closed_up_limit")) or bool((theme_row or {}).get("closed_up_limit")):
        score -= 0.35
    abnormal_turnover = _safe_float(stock_row.get("abnormal_turnover") if stock_row else None)
    if abnormal_turnover is not None and abnormal_turnover > 3.5:
        score -= 0.2
    return _clamp(score)


def _lifecourt_proxy_score(
    *,
    vcov_score: float,
    consensus_score: float,
    burst_score: float,
    price_confirm_score: float,
    crowding_score: float,
    hygiene_score: float,
    regime_score: float,
) -> float:
    raw = (
        0.18 * vcov_score
        + 0.14 * consensus_score
        + 0.14 * burst_score
        + 0.20 * price_confirm_score
        - 0.16 * crowding_score
        + 0.10 * hygiene_score
        + 0.08 * regime_score
    )
    return _clamp(raw)


def _percentile_threshold(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * quantile))))
    return ordered[index]


@dataclass(frozen=True)
class _LifeLongThresholds:
    lifecourt_min: float
    price_confirm_min: float
    crowding_max: float


def _life_long_thresholds(
    rows: list[dict[str, object]],
    *,
    thresholds: HybridFusionThresholds,
) -> _LifeLongThresholds:
    lifecourt_values = [cast(float, row["lifecourt_proxy_score"]) for row in rows]
    pconf_values = [cast(float, row["price_confirm_score"]) for row in rows]
    crowd_values = [cast(float, row["crowding_score"]) for row in rows]
    return _LifeLongThresholds(
        lifecourt_min=_percentile_threshold(lifecourt_values, thresholds.life_long_top_q),
        price_confirm_min=_percentile_threshold(pconf_values, thresholds.life_long_pconf_top_q),
        crowding_max=_percentile_threshold(crowd_values, thresholds.life_long_crowd_max_q),
    )


def _life_long_pass(row: dict[str, object], *, thresholds: _LifeLongThresholds) -> bool:
    return (
        cast(float, row["lifecourt_proxy_score"]) >= thresholds.lifecourt_min
        and cast(float, row["price_confirm_score"]) >= thresholds.price_confirm_min
        and cast(float, row["crowding_score"]) <= thresholds.crowding_max
        and cast(float, row["hygiene_score"]) > 0
    )


@dataclass(frozen=True)
class _StanceThresholds:
    cycle_strong_min: float
    cycle_neutral_min: float
    life_strong_min: float
    life_neutral_min: float


def _stance_thresholds(
    rows: list[dict[str, object]],
    *,
    thresholds: HybridFusionThresholds,
) -> _StanceThresholds:
    cycle_values = [cast(float, row["cycle_score"]) for row in rows]
    life_values = [cast(float, row["lifecourt_proxy_score"]) for row in rows]
    return _StanceThresholds(
        cycle_strong_min=_percentile_threshold(cycle_values, thresholds.stance_strong_q),
        cycle_neutral_min=_percentile_threshold(cycle_values, thresholds.stance_neutral_q),
        life_strong_min=_percentile_threshold(life_values, thresholds.stance_strong_q),
        life_neutral_min=_percentile_threshold(life_values, thresholds.stance_neutral_q),
    )


def _cycle_stance(cycle_score: float, *, thresholds: _StanceThresholds) -> str:
    if cycle_score >= thresholds.cycle_strong_min:
        return "strong"
    if cycle_score >= thresholds.cycle_neutral_min:
        return "neutral"
    return "weak"


def _life_stance(lifecourt_proxy_score: float, *, thresholds: _StanceThresholds) -> str:
    if lifecourt_proxy_score >= thresholds.life_strong_min:
        return "strong"
    if lifecourt_proxy_score >= thresholds.life_neutral_min:
        return "neutral"
    return "weak"


def _fusion_action(
    *,
    cycle_score: float,
    lifecourt_proxy_score: float,
    stance_thresholds: _StanceThresholds,
) -> str:
    cycle = _cycle_stance(cycle_score, thresholds=stance_thresholds)
    life = _life_stance(lifecourt_proxy_score, thresholds=stance_thresholds)
    matrix = {
        ("strong", "strong"): "core_plus_trading",
        ("strong", "neutral"): "core_reduce_trading",
        ("neutral", "strong"): "satellite_trial",
        ("weak", "strong"): "high_liquidity_trial_only",
        ("weak", "neutral"): "defensive_only",
        ("weak", "weak"): "clear_or_defensive",
        ("strong", "weak"): "core_only",
        ("neutral", "neutral"): "monitor_only",
        ("neutral", "weak"): "defensive_only",
    }
    return matrix.get((cycle, life), "monitor_only")


def _price_confirm_score(
    *,
    stock_row: dict[str, object] | None,
    theme_row: dict[str, object] | None,
) -> float:
    if stock_row:
        close_strength = _clamp(_safe_float(stock_row.get("close_strength")) or 0)
        abnormal_turnover = _clamp(((_safe_float(stock_row.get("abnormal_turnover")) or 0) - 1.0) / 1.4)
        extension = _safe_float(stock_row.get("breakout_extension_norm"))
        extension_score = 1.0 if extension is None else _clamp(1 - abs(extension - 0.12) / 0.35)
        return _clamp(0.45 * close_strength + 0.35 * abnormal_turnover + 0.2 * extension_score)
    if theme_row:
        close_strength = _clamp(_safe_float(theme_row.get("close_strength")) or 0)
        pctchange = _clamp((_safe_float(theme_row.get("pctchange")) or 0) / 10)
        turn = _clamp((_safe_float(theme_row.get("turn")) or 0) / 6)
        return _clamp(0.4 * close_strength + 0.35 * pctchange + 0.25 * turn)
    return 0.0


def _crowding_penalty(
    *,
    stock_row: dict[str, object] | None,
    theme_row: dict[str, object] | None,
) -> float:
    penalty = 0.0
    abnormal_turnover = _safe_float(stock_row.get("abnormal_turnover") if stock_row else None)
    if abnormal_turnover is not None and abnormal_turnover > 2.4:
        penalty += min(0.25, (abnormal_turnover - 2.4) / 6)
    turn = _safe_float(theme_row.get("turn") if theme_row else None)
    if turn is not None and turn > 8:
        penalty += min(0.2, (turn - 8) / 20)
    if bool((stock_row or {}).get("closed_up_limit")) or bool((theme_row or {}).get("closed_up_limit")):
        penalty += 0.12
    return _clamp(penalty)


def _confidence(source_kinds: list[str]) -> str:
    if len(source_kinds) >= 3:
        return "high"
    if len(source_kinds) == 2:
        return "medium"
    return "low"


def _reason(
    *,
    cycle_score: float,
    lifecourt_proxy_score: float,
    source_kinds: list[str],
    life_long_pass: bool | None = None,
    fusion_action: str | None = None,
) -> str:
    parts = [
        "Fusion observation-only candidate:",
        f"cycle {cycle_score:.2f}",
        f"lifecourt proxy {lifecourt_proxy_score:.2f}",
        f"sources {', '.join(source_kinds) or 'none'}",
    ]
    if life_long_pass is not None:
        parts.append(f"life_long {'pass' if life_long_pass else 'fail'}")
    if fusion_action:
        parts.append(f"action {fusion_action}")
    return ", ".join(parts) + "."


def _first_int(*values: object) -> int | None:
    for value in values:
        number = _safe_int(value)
        if number is not None:
            return number
    return None


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _safe_int(value: object) -> int | None:
    number = _safe_float(value)
    return None if number is None else int(number)


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))
