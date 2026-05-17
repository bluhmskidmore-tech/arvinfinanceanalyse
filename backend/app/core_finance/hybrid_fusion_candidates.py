from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

FORMULA_VERSION = "rv_hybrid_fusion_candidates_v1"
ACTIVE_MARKET_STATES = {"PENDING_DATA", "WARM", "HOT"}
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
) -> HybridFusionResult:
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
    scored: list[dict[str, object]] = []
    for stock_code in stock_codes:
        sources = _source_rows(
            stock_code=stock_code,
            stock_rows=stock_rows,
            factor_rows=factor_rows,
            theme_rows=theme_rows,
        )
        base = _first_row(sources)
        sector_code = _text(base.get("sector_code"))
        sector_rank = _first_int(
            stock_rows.get(stock_code, {}).get("sector_rank"),
            theme_rows.get(stock_code, {}).get("sector_rank"),
            sector_ranks.get(sector_code),
        )
        sector_score = _sector_score(sector_rank)
        factor_rank_score = _factor_rank_score(factor_rows.get(stock_code), factor_rank_count)
        cycle_score = _clamp(0.7 * sector_score + 0.3 * factor_rank_score)
        attention_score = _attention_score(theme_rows.get(stock_code))
        price_confirm_score = _price_confirm_score(
            stock_row=stock_rows.get(stock_code),
            theme_row=theme_rows.get(stock_code),
        )
        crowding_penalty = _crowding_penalty(
            stock_row=stock_rows.get(stock_code),
            theme_row=theme_rows.get(stock_code),
        )
        lifecourt_proxy_score = _clamp(0.5 * attention_score + 0.4 * price_confirm_score - crowding_penalty)
        fusion_score = round(0.65 * cycle_score + 0.35 * lifecourt_proxy_score, 6)
        source_kinds = _source_kinds(stock_code, stock_rows=stock_rows, factor_rows=factor_rows, theme_rows=theme_rows)
        scored.append(
            {
                "stock_code": stock_code,
                "stock_name": _text(base.get("stock_name")) or stock_code,
                "sector_code": sector_code,
                "sector_name": _text(base.get("sector_name")),
                "fusion_score": fusion_score,
                "cycle_score": round(cycle_score, 6),
                "lifecourt_proxy_score": round(lifecourt_proxy_score, 6),
                "attention_score": round(attention_score, 6),
                "price_confirm_score": round(price_confirm_score, 6),
                "crowding_penalty": round(crowding_penalty, 6),
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
                },
            }
        )

    ordered = sorted(
        scored,
        key=lambda row: (
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
            coverage_note="Hybrid fusion uses existing sector, factor, trend, and theme proxy inputs.",
        )
    )


def _build_payload(
    *,
    as_of_date: str,
    market_state: str,
    items: list[dict[str, object]],
    coverage_note: str,
) -> dict[str, object]:
    return {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "observation_only": True,
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


def _reason(*, cycle_score: float, lifecourt_proxy_score: float, source_kinds: list[str]) -> str:
    return (
        "Fusion observation-only candidate: "
        f"cycle {cycle_score:.2f}, lifecourt proxy {lifecourt_proxy_score:.2f}, "
        f"sources {', '.join(source_kinds) or 'none'}."
    )


def _first_int(*values: object) -> int | None:
    for value in values:
        number = _safe_int(value)
        if number is not None:
            return number
    return None


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
