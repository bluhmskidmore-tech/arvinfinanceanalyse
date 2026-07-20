from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "initial_capital": 200000.0,
    "universe": {
        "512480": {"name": "Semiconductor ETF", "role": "attack", "exchange": "SH", "limit_pct": 0.10},
        "159819": {"name": "AI ETF", "role": "attack", "exchange": "SZ", "limit_pct": 0.10},
        "512400": {"name": "Nonferrous Metals ETF", "role": "cycle", "exchange": "SH", "limit_pct": 0.10},
        "512000": {"name": "Brokerage ETF", "role": "defense", "exchange": "SH", "limit_pct": 0.10},
        "510880": {"name": "Dividend ETF", "role": "defense", "exchange": "SH", "limit_pct": 0.10},
    },
    "role_base_weight": {"attack": 0.45, "cycle": 0.25, "defense": 0.30},
    "base_position": 0.65,
    "macro_sensitivity": 0.25,
    "min_position": 0.30,
    "max_position": 0.90,
    "rebalance_weekday": 0,
    "cost_rate": 0.0005,
    "lot_size": 100,
    "min_trade_value": 2000.0,
    "cash_buffer_pct": 0.01,
    "max_single_order_pct": 0.25,
    "max_turnover_pct": 0.80,
    "limit_guard_ratio": 0.95,
    "earnings_windows": [
        ["2026-07-10", "2026-07-20"],
        ["2026-08-20", "2026-08-31"],
        ["2026-10-20", "2026-10-31"],
    ],
    "earnings_attack_scaler": 0.8,
    "risk_events": ["2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"],
    "event_lookahead": 3,
    "event_position_scaler": 0.9,
}

DEFAULT_MACRO_STATE: dict[str, Any] = {
    "updated": "2026-07-03",
    "scores": {
        "domestic_liquidity": 0.6,
        "external_liquidity": -0.5,
        "price_recovery": 0.2,
        "earnings_cycle": 0.3,
        "policy_support": 0.4,
        "geopolitical": 0.1,
    },
    "weights": {
        "domestic_liquidity": 0.25,
        "external_liquidity": 0.20,
        "price_recovery": 0.15,
        "earnings_cycle": 0.20,
        "policy_support": 0.10,
        "geopolitical": 0.10,
    },
}

MACRO_SCORE_KEYS = tuple(DEFAULT_MACRO_STATE["weights"].keys())


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any] | None) -> dict[str, Any]:
    result = dict(base)
    for key, value in dict(override or {}).items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_macro_etf_strategy_snapshot(
    *,
    config: Mapping[str, Any] | None = None,
    macro_state: Mapping[str, Any] | None = None,
    as_of_date: date,
    quotes: Mapping[str, Mapping[str, Any]] | None = None,
    portfolio_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = deep_merge(DEFAULT_CONFIG, config)
    macro = deep_merge(DEFAULT_MACRO_STATE, macro_state)
    warnings = _config_warnings(cfg, macro)
    macro_score = compute_macro_score(macro)
    total_position = compute_total_position(cfg, macro_score=macro_score, as_of_date=as_of_date)
    targets, target_notes = compute_target_weights(cfg, total_position=total_position, as_of_date=as_of_date)
    order_payload = build_order_drafts(
        targets=targets,
        config=cfg,
        quotes=quotes,
        portfolio_state=portfolio_state,
    )
    warnings.extend(order_payload["warnings"])
    updated = _text(macro.get("updated"))
    staleness_days = _staleness_days(updated, as_of_date)
    if staleness_days is not None and staleness_days > 45:
        warnings.append(f"macro_state updated {staleness_days} calendar days before as_of_date")
    status = "ready" if order_payload["draft_status"] == "ready" and not warnings else "warning"
    if order_payload["draft_status"] == "blocked":
        status = "blocked"
    return {
        "strategy_name": "macro_etf_rotation_observation",
        "boundary": "observation_only",
        "execution_enabled": False,
        "as_of_date": as_of_date.isoformat(),
        "macro": {
            "score": round(macro_score, 6),
            "updated": updated,
            "staleness_days": staleness_days,
            "scores": {key: _float(macro.get("scores", {}).get(key), 0.0) for key in MACRO_SCORE_KEYS},
            "weights": {key: _float(macro.get("weights", {}).get(key), 0.0) for key in MACRO_SCORE_KEYS},
        },
        "position": {
            "target_total_weight": round(total_position, 6),
            "cash_weight": round(max(0.0, 1.0 - sum(targets.values())), 6),
            "target_weights": {code: round(weight, 6) for code, weight in targets.items()},
            "notes": target_notes,
        },
        "order_draft": {
            key: value
            for key, value in order_payload.items()
            if key not in {"warnings"}
        },
        "risk_controls": _risk_controls(cfg),
        "warnings": warnings,
        "data_status": {
            "status": status,
            "quote_status": order_payload["quote_status"],
            "state_status": order_payload["state_status"],
        },
        "provenance": {
            "source_script": "C:/Users/arvin/Desktop/files.zip/live_macro_strategy.py",
            "integration_mode": "ported_read_only_without_modifying_source_script",
            "deferred_controls": [
                "trend_ma_filter_requires_history_adapter",
                "crowding_shift_requires_amount_history_adapter",
                "sector_stop_loss_monitor_requires_intraday_state_adapter",
                "broker_execution_disabled_in_moss",
            ],
        },
    }


def compute_macro_score(macro_state: Mapping[str, Any]) -> float:
    scores = macro_state.get("scores", {})
    weights = macro_state.get("weights", {})
    score = sum(_float(scores.get(key), 0.0) * _float(weights.get(key), 0.0) for key in MACRO_SCORE_KEYS)
    return _clip(score, -1.0, 1.0)


def compute_total_position(config: Mapping[str, Any], *, macro_score: float, as_of_date: date) -> float:
    position = _float(config.get("base_position"), 0.0) + _float(config.get("macro_sensitivity"), 0.0) * macro_score
    position = _clip(position, _float(config.get("min_position"), 0.0), _float(config.get("max_position"), 1.0))
    if _near_risk_event(config, as_of_date):
        position *= _float(config.get("event_position_scaler"), 1.0)
    return position


def compute_target_weights(
    config: Mapping[str, Any],
    *,
    total_position: float,
    as_of_date: date,
) -> tuple[dict[str, float], list[str]]:
    universe = _universe(config)
    role_base = dict(config.get("role_base_weight") or {})
    roles: dict[str, list[str]] = {}
    for code, meta in universe.items():
        roles.setdefault(_text(meta.get("role")), []).append(code)
    weights: dict[str, float] = {}
    for role, codes in roles.items():
        if not codes:
            continue
        base_weight = _float(role_base.get(role), 0.0)
        for code in codes:
            weights[code] = base_weight / len(codes)
    notes = [f"macro score sets total position to {total_position:.1%}"]
    if _in_earnings_window(config, as_of_date):
        attack_codes = roles.get("attack", [])
        for code in attack_codes:
            weights[code] = weights.get(code, 0.0) * _float(config.get("earnings_attack_scaler"), 1.0)
        if attack_codes:
            notes.append("earnings window scales attack sleeve")
    if _near_risk_event(config, as_of_date):
        notes.append("near configured risk event, total position scaled")
    return {code: weights.get(code, 0.0) * total_position for code in universe}, notes


def build_order_drafts(
    *,
    targets: Mapping[str, float],
    config: Mapping[str, Any],
    quotes: Mapping[str, Mapping[str, Any]] | None,
    portfolio_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    universe = _universe(config)
    if not quotes:
        return _blocked_orders("quotes_missing", "No quote snapshot supplied; order drafts are suppressed.")
    missing_quotes = [code for code in universe if code not in quotes]
    if missing_quotes:
        return _blocked_orders("quotes_incomplete", f"Missing quote snapshot for: {', '.join(missing_quotes)}")

    state = dict(portfolio_state or {})
    holdings = dict(state.get("holdings") or {})
    cash = _float(state.get("cash"), _float(config.get("initial_capital"), 0.0))
    lot = max(1, int(_float(config.get("lot_size"), 100)))
    nav = cash + sum(_shares(holdings.get(code)) * _quote_price(quotes[code]) for code in universe)
    warnings: list[str] = []
    sells: list[dict[str, Any]] = []
    buys: list[dict[str, Any]] = []
    for code, meta in universe.items():
        quote = quotes[code]
        price = _quote_price(quote)
        volume = _float(quote.get("volume"), 0.0)
        prev_close = _float(quote.get("prev_close"), price)
        if price <= 0 or volume <= 0:
            warnings.append(f"{code} quote is invalid or volume is zero; suppressing this symbol")
            continue
        target_shares = int((targets.get(code, 0.0) * nav / price) // lot) * lot
        current_shares = _shares(holdings.get(code))
        diff = target_shares - current_shares
        if diff == 0:
            continue
        if abs(diff) * price < _float(config.get("min_trade_value"), 0.0):
            continue
        max_single_value = _float(config.get("max_single_order_pct"), 1.0) * nav
        if abs(diff) * price > max_single_value:
            warnings.append(f"{code} order value exceeded max_single_order_pct and was clipped")
            diff = int((1 if diff > 0 else -1) * (max_single_value / price // lot) * lot)
            if diff == 0:
                continue
        order = _order_base(code, meta, price, reason="rebalance_review")
        if diff < 0:
            sells.append({**order, "side": "SELL", "shares": -diff})
        else:
            change = price / prev_close - 1.0 if prev_close > 0 else 0.0
            limit_pct = _float(meta.get("limit_pct"), 0.10)
            if change > limit_pct * _float(config.get("limit_guard_ratio"), 0.95):
                warnings.append(f"{code} is near configured upper limit; buy draft suppressed")
                continue
            buys.append({**order, "side": "BUY", "shares": diff})

    projected_cash = cash + sum(order["shares"] * order["ref_price"] * (1 - _float(config.get("cost_rate"), 0.0)) for order in sells)
    projected_cash -= nav * _float(config.get("cash_buffer_pct"), 0.0)
    accepted_buys: list[dict[str, Any]] = []
    for buy in sorted(buys, key=lambda item: item["shares"] * item["ref_price"], reverse=True):
        need = buy["shares"] * buy["ref_price"] * (1 + _float(config.get("cost_rate"), 0.0))
        if need <= projected_cash:
            accepted_buys.append(buy)
            projected_cash -= need
            continue
        fit = int(projected_cash / (buy["ref_price"] * (1 + _float(config.get("cost_rate"), 0.0))) // lot) * lot
        if fit >= lot:
            accepted_buys.append({**buy, "shares": fit})
            projected_cash -= fit * buy["ref_price"] * (1 + _float(config.get("cost_rate"), 0.0))
            warnings.append(f"{buy['code']} buy draft reduced to {fit} shares by cash constraint")
        else:
            warnings.append(f"{buy['code']} buy draft suppressed by cash constraint")

    orders = [_with_order_value(order) for order in sells + accepted_buys]
    turnover = sum(order["notional"] for order in orders) / max(nav, 1e-9)
    if turnover > _float(config.get("max_turnover_pct"), 1.0):
        return {
            **_blocked_orders("turnover_limit", "Order draft turnover exceeded max_turnover_pct."),
            "warnings": warnings,
            "nav": round(nav, 2),
            "turnover": round(turnover, 6),
        }
    return {
        "draft_status": "ready",
        "quote_status": "ready",
        "state_status": "provided" if portfolio_state else "default_initial_cash",
        "nav": round(nav, 2),
        "turnover": round(turnover, 6),
        "orders": orders,
        "order_count": len(orders),
        "execution_policy": "manual_review_only",
        "warnings": warnings,
    }


def _blocked_orders(reason_code: str, reason: str) -> dict[str, Any]:
    return {
        "draft_status": "blocked",
        "quote_status": reason_code,
        "state_status": "not_evaluated",
        "nav": None,
        "turnover": None,
        "orders": [],
        "order_count": 0,
        "execution_policy": "manual_review_only",
        "blocked_reason": reason,
        "warnings": [reason],
    }


def _risk_controls(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lot_size": int(_float(config.get("lot_size"), 100)),
        "min_trade_value": _float(config.get("min_trade_value"), 0.0),
        "cash_buffer_pct": _float(config.get("cash_buffer_pct"), 0.0),
        "max_single_order_pct": _float(config.get("max_single_order_pct"), 1.0),
        "max_turnover_pct": _float(config.get("max_turnover_pct"), 1.0),
        "limit_guard_ratio": _float(config.get("limit_guard_ratio"), 0.95),
    }


def _config_warnings(config: Mapping[str, Any], macro_state: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    universe = _universe(config)
    if not universe:
        warnings.append("strategy universe is empty")
    for key in MACRO_SCORE_KEYS:
        score = _float((macro_state.get("scores") or {}).get(key), 0.0)
        if score < -1.0 or score > 1.0:
            warnings.append(f"macro score {key} is outside [-1, 1]")
    return warnings


def _in_earnings_window(config: Mapping[str, Any], as_of_date: date) -> bool:
    for item in config.get("earnings_windows") or []:
        if not isinstance(item, list | tuple) or len(item) != 2:
            continue
        start = _date_or_none(item[0])
        end = _date_or_none(item[1])
        if start is not None and end is not None and start <= as_of_date <= end:
            return True
    return False


def _near_risk_event(config: Mapping[str, Any], as_of_date: date) -> bool:
    lookahead = int(_float(config.get("event_lookahead"), 0))
    for value in config.get("risk_events") or []:
        event_date = _date_or_none(value)
        if event_date is None:
            continue
        days = (event_date - as_of_date).days
        if 0 <= days <= lookahead + 2:
            return True
    return False


def _staleness_days(updated: str | None, as_of_date: date) -> int | None:
    updated_date = _date_or_none(updated)
    if updated_date is None:
        return None
    return (as_of_date - updated_date).days


def _date_or_none(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def _universe(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = config.get("universe")
    if not isinstance(raw, Mapping):
        return {}
    return {str(code): meta for code, meta in raw.items() if isinstance(meta, Mapping)}


def _order_base(code: str, meta: Mapping[str, Any], price: float, *, reason: str) -> dict[str, Any]:
    return {
        "code": code,
        "name": _text(meta.get("name")) or code,
        "exchange": _text(meta.get("exchange")),
        "ref_price": round(price, 3),
        "reason": reason,
    }


def _with_order_value(order: Mapping[str, Any]) -> dict[str, Any]:
    notional = int(order["shares"]) * float(order["ref_price"])
    return {
        **dict(order),
        "notional": round(notional, 2),
    }


def _quote_price(quote: Mapping[str, Any]) -> float:
    return _float(quote.get("price"), 0.0)


def _shares(raw: object) -> int:
    if isinstance(raw, Mapping):
        return int(_float(raw.get("shares"), 0.0))
    return int(_float(raw, 0.0))


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
