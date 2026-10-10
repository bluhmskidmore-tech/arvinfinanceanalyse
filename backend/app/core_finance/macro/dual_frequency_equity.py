from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

FORMULA_VERSION = "a_share_dual_frequency_v6_moss_v1"
RULE_VERSION = "dual_frequency_equity_candidate_v1"

DEFAULT_CONFIG: dict[str, float | int] = {
    "high_window": 20,
    "high_amount_ratio": 1.5,
    "thrust_window": 5,
    "thrust_return": 0.05,
    "thrust_amount_ratio": 1.3,
    "atr_window": 20,
    "atr_multiple": 3.0,
    "exit_ma_window": 60,
    "exit_below_days": 2,
    "defense_multiplier": 0.4,
    "fast_drawdown_window": 5,
    "fast_drawdown_threshold": -0.10,
    "halve_drawdown_threshold": -0.20,
    "kill_drawdown_threshold": -0.30,
    "restore_drawdown_threshold": -0.10,
    "cooldown_days": 60,
    "resume_temperature": 55.0,
    "ramp_days": 20,
}


def build_dual_frequency_equity_snapshot(
    *,
    daily_rows: Sequence[Mapping[str, Any]] | None,
    slow_cap: float | None,
    as_of_date: date,
    nav_rows: Sequence[Mapping[str, Any]] | None = None,
    nav_history_authoritative_complete: bool = False,
    survival_state: Mapping[str, Any] | None = None,
    resume_temperature: float | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a pure, observation-only dual-frequency equity strategy snapshot.

    ``daily_rows`` must provide ``trade_date``, ``close`` and ``amount``.
    ``amount`` must already be a single-unit series (the repository layer
    normalizes choice_stock_daily_observation to RMB across vendor
    generations per docs/data_contracts.md §4.10). The amount-ratio
    thresholds (``high_amount_ratio``/``thrust_amount_ratio``) are
    dimensionless and only meaningful when every row shares that unit;
    feeding mixed-unit rows fabricates attack/exit transitions at the
    vendor boundary. The
    slow layer is deliberately limited to an upstream-supplied cap; this
    function does not reinterpret a macro score as a temperature or risk
    budget. A final target is emitted only when the survival layer can be
    evaluated from NAV history explicitly confirmed authoritative and complete
    from strategy inception, or from a date-aligned authoritative state.
    """

    cfg = _validated_config(config)
    market_rows, market_quality = _normalise_market_rows(daily_rows, as_of_date=as_of_date)
    slow, slow_warnings = _build_slow_layer(slow_cap)
    fast, fast_events, fast_warnings = _build_fast_layer(market_rows, cfg)
    signal_date = _parse_date(fast.get("signal_date"))
    survival, survival_events, survival_warnings = _build_survival_layer(
        nav_rows=nav_rows,
        nav_history_authoritative_complete=nav_history_authoritative_complete,
        survival_state=survival_state,
        resume_temperature=resume_temperature,
        expected_date=signal_date,
        as_of_date=as_of_date,
        config=cfg,
    )

    pre_survival_target = None
    if slow["status"] == "ready" and fast["status"] == "ready":
        pre_survival_target = _round_weight(float(slow["cap"]) * float(fast["multiplier"]))

    final_target = None
    if pre_survival_target is not None and survival["status"] == "ready":
        final_target = _round_weight(pre_survival_target * float(survival["multiplier"]))

    warnings = [
        *market_quality["warnings"],
        *slow_warnings,
        *fast_warnings,
        *survival_warnings,
    ]
    if final_target is None:
        warnings.append(
            "Final target is withheld until slow, fast, and survival layers are all evaluable."
        )
    warnings = _dedupe(warnings)

    if slow["status"] != "ready" or fast["status"] == "insufficient":
        overall_status = "insufficient"
    elif final_target is None or market_quality["status"] != "ready":
        overall_status = "degraded"
    else:
        overall_status = "ready"

    latest_trade_date = market_quality["latest_trade_date"]
    return {
        "strategy_name": "a_share_dual_frequency_equity_candidate",
        "boundary": "observation_only",
        "execution_enabled": False,
        "formula_version": FORMULA_VERSION,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of_date.isoformat(),
        "slow": slow,
        "fast": fast,
        "survival": survival,
        "pre_survival_target_total_weight": pre_survival_target,
        "final_target_total_weight": final_target,
        "events": [*fast_events, *survival_events],
        "warnings": warnings,
        "data_status": {
            "status": overall_status,
            "market_history_status": market_quality["status"],
            "slow_cap_status": slow["status"],
            "fast_status": fast["status"],
            "survival_status": survival["status"],
            "input_row_count": market_quality["input_row_count"],
            "usable_row_count": market_quality["usable_row_count"],
            "invalid_row_count": market_quality["invalid_row_count"],
            "duplicate_date_count": market_quality["duplicate_date_count"],
            "latest_trade_date": latest_trade_date,
            "as_of_alignment": (
                "no_observation"
                if latest_trade_date is None
                else "exact"
                if latest_trade_date == as_of_date.isoformat()
                else "prior_observation"
            ),
        },
        "methodology": {
            "slow_layer": (
                "Uses only the upstream slow_cap in [0, 1]; no macro-score-to-temperature "
                "mapping is performed."
            ),
            "fast_entry": (
                "Attack on a current-inclusive 20-session close high with amount ratio >= 1.5, "
                "or a 5-session return >= 5% with amount ratio >= 1.3."
            ),
            "fast_exit": (
                "Defense on close below the attack-period highest close minus 3 times ATR20, "
                "or on 2 consecutive closes below MA60."
            ),
            "atr_proxy": (
                "Index-close ATR proxy: rolling mean(abs(close.pct_change()), 20) multiplied "
                "by current close; intraday high-low data is not used."
            ),
            "amount_ratio": "Current amount divided by the current-inclusive 20-session mean amount.",
            "survival_layer": (
                "Uses supplied portfolio NAV/state only. NAV replay requires an explicit "
                "confirmation that history is authoritative and complete from strategy inception; "
                "an index or other market proxy is never substituted."
            ),
            "execution_timing": (
                "The snapshot describes information available through signal_date and does not "
                "model an executable fill."
            ),
        },
        "provenance": {
            "calculation_module": "backend.app.core_finance.macro.dual_frequency_equity",
            "source_strategy": "desktop:a_share_dual_freq_v6.py",
            "integration_mode": "ported_read_only_candidate",
            "slow_cap_source": "upstream_input",
            "fast_input_fields": ["trade_date", "close", "amount"],
            "survival_input_source": survival["source"],
            "nav_history_authoritative_complete": (
                nav_history_authoritative_complete is True
            ),
            "signal_date": fast.get("signal_date"),
            "latest_trade_date": latest_trade_date,
        },
    }


def _build_slow_layer(slow_cap: float | None) -> tuple[dict[str, Any], list[str]]:
    cap = _finite_float(slow_cap)
    if cap is None:
        return (
            {
                "status": "insufficient",
                "cap": None,
                "source": "upstream_input",
                "reason": "slow_cap_missing_or_non_numeric",
            },
            ["An upstream slow_cap is required; no macro score mapping was inferred."],
        )
    if cap < 0.0 or cap > 1.0:
        return (
            {
                "status": "insufficient",
                "cap": None,
                "source": "upstream_input",
                "reason": "slow_cap_out_of_range",
            },
            [f"slow_cap must be within [0, 1]; received {cap!r} and did not clip it."],
        )
    return (
        {
            "status": "ready",
            "cap": _round_weight(cap),
            "source": "upstream_input",
            "reason": None,
        },
        [],
    )


def _build_fast_layer(
    rows: Sequence[dict[str, Any]],
    config: Mapping[str, float | int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    minimum_rows = int(config["exit_ma_window"]) + 1
    if len(rows) < minimum_rows:
        latest_date = rows[-1]["trade_date"].isoformat() if rows else None
        return (
            {
                "status": "insufficient",
                "state": None,
                "multiplier": None,
                "signal_date": latest_date,
                "minimum_required_rows": minimum_rows,
                "available_rows": len(rows),
                "last_transition": None,
                "latest_metrics": None,
            },
            [],
            [
                f"Fast layer requires at least {minimum_rows} usable daily observations; "
                f"received {len(rows)}."
            ],
        )

    closes = [float(row["close"]) for row in rows]
    amounts = [float(row["amount"]) for row in rows]
    absolute_returns = [None]
    absolute_returns.extend(
        abs(closes[index] / closes[index - 1] - 1.0)
        for index in range(1, len(closes))
    )

    high_window = int(config["high_window"])
    thrust_window = int(config["thrust_window"])
    atr_window = int(config["atr_window"])
    ma_window = int(config["exit_ma_window"])
    start_index = ma_window
    state = "defense"
    highest_close_since_attack: float | None = None
    below_ma_count = 0
    events: list[dict[str, Any]] = []
    latest_metrics: dict[str, Any] | None = None

    for index in range(start_index, len(rows)):
        close = closes[index]
        amount_mean = sum(amounts[index - high_window + 1 : index + 1]) / high_window
        amount_ratio = amount_mean and amounts[index] / amount_mean
        high_20 = max(closes[index - high_window + 1 : index + 1])
        return_5 = close / closes[index - thrust_window] - 1.0
        atr_returns = absolute_returns[index - atr_window + 1 : index + 1]
        atr_proxy = (
            sum(float(value) for value in atr_returns if value is not None)
            / atr_window
            * close
        )
        ma_60 = sum(closes[index - ma_window + 1 : index + 1]) / ma_window
        transition: dict[str, Any] | None = None

        if state == "defense":
            high_trigger = (
                close >= high_20 - 1e-9
                and amount_ratio >= float(config["high_amount_ratio"])
            )
            thrust_trigger = (
                return_5 >= float(config["thrust_return"])
                and amount_ratio >= float(config["thrust_amount_ratio"])
            )
            below_ma_count = 0
            if high_trigger or thrust_trigger:
                state = "attack"
                highest_close_since_attack = close
                reason = "high_amount_breakout" if high_trigger else "five_day_thrust"
                transition = _fast_event(
                    row_date=rows[index]["trade_date"],
                    state=state,
                    reason=reason,
                    close=close,
                    amount_ratio=amount_ratio,
                    return_5=return_5,
                )
        else:
            highest_close_since_attack = max(float(highest_close_since_attack), close)
            below_ma_count = below_ma_count + 1 if close < ma_60 else 0
            chandelier_level = highest_close_since_attack - float(config["atr_multiple"]) * atr_proxy
            chandelier_exit = close < chandelier_level
            ma_exit = below_ma_count >= int(config["exit_below_days"])
            if chandelier_exit or ma_exit:
                state = "defense"
                reason = "chandelier_exit" if chandelier_exit else "two_closes_below_ma60"
                transition = _fast_event(
                    row_date=rows[index]["trade_date"],
                    state=state,
                    reason=reason,
                    close=close,
                    amount_ratio=amount_ratio,
                    return_5=return_5,
                )
                highest_close_since_attack = None
                below_ma_count = 0

        if transition is not None:
            events.append(transition)
        latest_metrics = {
            "close": _round_metric(close),
            "high_20": _round_metric(high_20),
            "amount_ratio_20": _round_metric(amount_ratio),
            "return_5": _round_metric(return_5),
            "atr_proxy_20": _round_metric(atr_proxy),
            "ma_60": _round_metric(ma_60),
            "highest_close_since_attack": (
                _round_metric(highest_close_since_attack)
                if highest_close_since_attack is not None
                else None
            ),
            "consecutive_closes_below_ma60": below_ma_count,
        }

    signal_date = rows[-1]["trade_date"].isoformat()
    return (
        {
            "status": "ready",
            "state": state,
            "multiplier": (
                1.0 if state == "attack" else _round_weight(float(config["defense_multiplier"]))
            ),
            "signal_date": signal_date,
            "minimum_required_rows": minimum_rows,
            "available_rows": len(rows),
            "last_transition": events[-1] if events else None,
            "latest_metrics": latest_metrics,
        },
        events,
        [],
    )


def _fast_event(
    *,
    row_date: date,
    state: str,
    reason: str,
    close: float,
    amount_ratio: float,
    return_5: float,
) -> dict[str, Any]:
    return {
        "layer": "fast",
        "date": row_date.isoformat(),
        "event": "enter_attack" if state == "attack" else "enter_defense",
        "state": state,
        "reason": reason,
        "close": _round_metric(close),
        "amount_ratio_20": _round_metric(amount_ratio),
        "return_5": _round_metric(return_5),
    }


def _build_survival_layer(
    *,
    nav_rows: Sequence[Mapping[str, Any]] | None,
    nav_history_authoritative_complete: bool,
    survival_state: Mapping[str, Any] | None,
    resume_temperature: float | None,
    expected_date: date | None,
    as_of_date: date,
    config: Mapping[str, float | int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    state_evaluation: tuple[dict[str, Any], list[dict[str, Any]], list[str]] | None = None
    if survival_state:
        state_evaluation = _survival_from_authoritative_state(
            survival_state=survival_state,
            expected_date=expected_date,
        )
        if state_evaluation[0]["status"] == "ready":
            return state_evaluation

    nav_evaluation: tuple[dict[str, Any], list[dict[str, Any]], list[str]] | None = None
    if nav_rows and nav_history_authoritative_complete is True:
        nav_evaluation = _survival_from_nav(
            nav_rows=nav_rows,
            resume_temperature=resume_temperature,
            expected_date=expected_date,
            as_of_date=as_of_date,
            config=config,
        )
    elif nav_rows:
        nav_evaluation = (
            _insufficient_survival(
                source="portfolio_nav_history",
                signal_date=expected_date,
                reason="nav_history_not_confirmed_authoritative_complete",
            ),
            [],
            [
                "Portfolio NAV rows were supplied without explicit confirmation that the "
                "history is authoritative and complete from strategy inception; replay was "
                "suppressed and the final target was withheld."
            ],
        )

    if nav_evaluation is not None and nav_evaluation[0]["status"] == "ready":
        if state_evaluation is None:
            return nav_evaluation
        return (
            nav_evaluation[0],
            nav_evaluation[1],
            [
                *state_evaluation[2],
                "Authoritative survival state was insufficient; complete portfolio NAV "
                "history was used instead.",
                *nav_evaluation[2],
            ],
        )

    if state_evaluation is not None and nav_evaluation is not None:
        return (
            _insufficient_survival(
                source="portfolio_survival_inputs",
                signal_date=expected_date,
                reason="authoritative_state_and_nav_history_insufficient",
            ),
            [],
            [
                *state_evaluation[2],
                *nav_evaluation[2],
                "Neither the authoritative survival state nor the supplied portfolio NAV "
                "history could evaluate the survival layer; the final target was withheld.",
            ],
        )
    if state_evaluation is not None:
        return state_evaluation
    if nav_evaluation is not None:
        return nav_evaluation
    return (
        {
            "status": "not_evaluated",
            "source": "not_supplied",
            "state": None,
            "multiplier": None,
            "signal_date": expected_date.isoformat() if expected_date else None,
            "current_drawdown": None,
            "five_day_drawdown": None,
            "halved": None,
            "killed": None,
            "cooldown_remaining": None,
            "ramp_remaining": None,
            "reason": "authoritative_portfolio_nav_or_state_not_supplied",
        },
        [],
        [
            "Survival layer was not evaluated because authoritative portfolio NAV/state "
            "was not supplied; an index proxy was not substituted."
        ],
    )


def _survival_from_nav(
    *,
    nav_rows: Sequence[Mapping[str, Any]],
    resume_temperature: float | None,
    expected_date: date | None,
    as_of_date: date,
    config: Mapping[str, float | int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    rows, quality = _normalise_nav_rows(nav_rows, as_of_date=as_of_date)
    minimum_rows = int(config["fast_drawdown_window"]) + 1
    latest_date = rows[-1]["trade_date"] if rows else None
    warnings = list(quality["warnings"])
    if len(rows) < minimum_rows:
        warnings.append(
            f"Survival layer requires at least {minimum_rows} usable NAV observations; "
            f"received {len(rows)}."
        )
        return (
            _insufficient_survival(
                source="portfolio_nav_history",
                signal_date=latest_date,
                reason="nav_history_too_short",
            ),
            [],
            warnings,
        )
    if expected_date is None or latest_date != expected_date:
        warnings.append(
            "Latest portfolio NAV date does not match the fast signal date; final target "
            "was withheld."
        )
        return (
            _insufficient_survival(
                source="portfolio_nav_history",
                signal_date=latest_date,
                reason="nav_date_not_aligned_to_fast_signal",
            ),
            [],
            warnings,
        )
    if quality["status"] != "ready":
        warnings.append("Invalid or duplicate NAV observations prevent authoritative evaluation.")
        return (
            _insufficient_survival(
                source="portfolio_nav_history",
                signal_date=latest_date,
                reason="nav_history_quality_degraded",
            ),
            [],
            warnings,
        )

    nav_history: list[float] = []
    peak = float(rows[0]["nav"])
    halved = False
    killed = False
    cooldown_remaining = 0
    ramp_remaining = 0
    events: list[dict[str, Any]] = []
    current_drawdown = 0.0
    five_day_drawdown = 0.0
    missing_resume_temperature = False

    for index, row in enumerate(rows):
        nav = float(row["nav"])
        nav_history.append(nav)
        peak = max(peak, nav)
        current_drawdown = nav / peak - 1.0
        trailing_peak = max(
            nav_history[-(int(config["fast_drawdown_window"]) + 1) :]
        )
        five_day_drawdown = nav / trailing_peak - 1.0
        temperature = _finite_float(row.get("temperature"))
        if (
            temperature is None
            and index == len(rows) - 1
            and resume_temperature is not None
        ):
            temperature = _finite_float(resume_temperature)

        multiplier = 1.0
        if killed:
            cooldown_remaining -= 1
            if (
                cooldown_remaining <= 0
                and temperature is not None
                and temperature >= float(config["resume_temperature"])
            ):
                killed = False
                peak = nav
                current_drawdown = 0.0
                ramp_remaining = int(config["ramp_days"])
                events.append(
                    _survival_event(
                        row["trade_date"],
                        event="resume",
                        current_drawdown=current_drawdown,
                        five_day_drawdown=five_day_drawdown,
                        detail=f"temperature={temperature:.6g}",
                    )
                )
            else:
                multiplier = 0.0
                if cooldown_remaining <= 0 and temperature is None:
                    missing_resume_temperature = True

        if not killed:
            if current_drawdown <= float(config["kill_drawdown_threshold"]):
                killed = True
                cooldown_remaining = int(config["cooldown_days"])
                multiplier = 0.0
                halved = False
                events.append(
                    _survival_event(
                        row["trade_date"],
                        event="kill",
                        current_drawdown=current_drawdown,
                        five_day_drawdown=five_day_drawdown,
                        detail="peak_drawdown_threshold",
                    )
                )
            else:
                if (
                    not halved
                    and (
                        current_drawdown <= float(config["halve_drawdown_threshold"])
                        or five_day_drawdown <= float(config["fast_drawdown_threshold"])
                    )
                ):
                    halved = True
                    detail = (
                        "five_day_drawdown_threshold"
                        if (
                            five_day_drawdown <= float(config["fast_drawdown_threshold"])
                            and current_drawdown > float(config["halve_drawdown_threshold"])
                        )
                        else "peak_drawdown_threshold"
                    )
                    events.append(
                        _survival_event(
                            row["trade_date"],
                            event="halve",
                            current_drawdown=current_drawdown,
                            five_day_drawdown=five_day_drawdown,
                            detail=detail,
                        )
                    )
                if (
                    halved
                    and current_drawdown > float(config["restore_drawdown_threshold"])
                    and five_day_drawdown > float(config["fast_drawdown_threshold"])
                ):
                    halved = False
                    events.append(
                        _survival_event(
                            row["trade_date"],
                            event="restore",
                            current_drawdown=current_drawdown,
                            five_day_drawdown=five_day_drawdown,
                            detail="drawdowns_recovered",
                        )
                    )

        if not killed:
            if ramp_remaining > 0:
                ramp_remaining -= 1
                multiplier = 0.5
            elif halved:
                multiplier = 0.5
    if missing_resume_temperature:
        warnings.append(
            "Cooldown elapsed while killed, but resume temperature was unavailable; "
            "the strategy remained killed."
        )
    state = "killed" if killed else "ramp" if ramp_remaining > 0 else "halved" if halved else "normal"
    return (
        {
            "status": "ready",
            "source": "portfolio_nav_history",
            "state": state,
            "multiplier": _round_weight(multiplier),
            "signal_date": latest_date.isoformat(),
            "current_drawdown": _round_metric(current_drawdown),
            "five_day_drawdown": _round_metric(five_day_drawdown),
            "peak_nav": _round_metric(peak),
            "current_nav": _round_metric(float(rows[-1]["nav"])),
            "halved": halved,
            "killed": killed,
            "cooldown_remaining": max(0, cooldown_remaining),
            "ramp_remaining": ramp_remaining,
            "reason": None,
        },
        events,
        warnings,
    )


def _survival_from_authoritative_state(
    *,
    survival_state: Mapping[str, Any],
    expected_date: date | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    state_date = _parse_date(
        survival_state.get("signal_date")
        or survival_state.get("as_of_date")
        or survival_state.get("trade_date")
    )
    if survival_state.get("authoritative") is not True:
        return (
            _insufficient_survival(
                source="portfolio_survival_state",
                signal_date=state_date,
                reason="state_not_marked_authoritative",
            ),
            [],
            ["Supplied survival state was not marked authoritative; final target was withheld."],
        )
    if expected_date is None or state_date != expected_date:
        return (
            _insufficient_survival(
                source="portfolio_survival_state",
                signal_date=state_date,
                reason="state_date_not_aligned_to_fast_signal",
            ),
            [],
            ["Authoritative survival state date does not match the fast signal date."],
        )

    killed = survival_state.get("killed")
    halved = survival_state.get("halved")
    cooldown = _nonnegative_int(survival_state.get("cooldown_remaining"))
    ramp = _nonnegative_int(survival_state.get("ramp_remaining"))
    if not isinstance(killed, bool) or not isinstance(halved, bool) or cooldown is None or ramp is None:
        return (
            _insufficient_survival(
                source="portfolio_survival_state",
                signal_date=state_date,
                reason="state_fields_missing_or_invalid",
            ),
            [],
            [
                "Authoritative survival state requires boolean killed/halved and non-negative "
                "cooldown_remaining/ramp_remaining."
            ],
        )
    multiplier = 0.0 if killed else 0.5 if halved or ramp > 0 else 1.0
    state = "killed" if killed else "ramp" if ramp > 0 else "halved" if halved else "normal"
    return (
        {
            "status": "ready",
            "source": "portfolio_survival_state",
            "state": state,
            "multiplier": multiplier,
            "signal_date": state_date.isoformat(),
            "current_drawdown": _optional_rounded_metric(
                survival_state.get("current_drawdown")
            ),
            "five_day_drawdown": _optional_rounded_metric(
                survival_state.get("five_day_drawdown")
            ),
            "peak_nav": _optional_rounded_metric(survival_state.get("peak_nav")),
            "current_nav": _optional_rounded_metric(survival_state.get("current_nav")),
            "halved": halved,
            "killed": killed,
            "cooldown_remaining": cooldown,
            "ramp_remaining": ramp,
            "reason": None,
        },
        [],
        [],
    )


def _survival_event(
    row_date: date,
    *,
    event: str,
    current_drawdown: float,
    five_day_drawdown: float,
    detail: str,
) -> dict[str, Any]:
    return {
        "layer": "survival",
        "date": row_date.isoformat(),
        "event": event,
        "current_drawdown": _round_metric(current_drawdown),
        "five_day_drawdown": _round_metric(five_day_drawdown),
        "detail": detail,
    }


def _insufficient_survival(
    *,
    source: str,
    signal_date: date | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": "insufficient",
        "source": source,
        "state": None,
        "multiplier": None,
        "signal_date": signal_date.isoformat() if signal_date else None,
        "current_drawdown": None,
        "five_day_drawdown": None,
        "halved": None,
        "killed": None,
        "cooldown_remaining": None,
        "ramp_remaining": None,
        "reason": reason,
    }


def _normalise_market_rows(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    as_of_date: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_rows = list(rows or [])
    normalised: dict[date, dict[str, Any]] = {}
    invalid_count = 0
    duplicate_count = 0
    future_count = 0
    for row in input_rows:
        if not isinstance(row, Mapping):
            invalid_count += 1
            continue
        row_date = _parse_date(row.get("trade_date") or row.get("date"))
        close = _finite_float(row.get("close"))
        amount = _finite_float(row.get("amount"))
        if row_date is None or close is None or close <= 0 or amount is None or amount <= 0:
            invalid_count += 1
            continue
        if row_date > as_of_date:
            future_count += 1
            continue
        if row_date in normalised:
            duplicate_count += 1
        normalised[row_date] = {"trade_date": row_date, "close": close, "amount": amount}
    usable = [normalised[key] for key in sorted(normalised)]
    warnings: list[str] = []
    if invalid_count:
        warnings.append(f"Dropped {invalid_count} invalid market history row(s).")
    if duplicate_count:
        warnings.append(
            f"Found {duplicate_count} duplicate market date(s); retained the last supplied row."
        )
    if future_count:
        warnings.append(
            f"Ignored {future_count} market history row(s) after requested as_of_date."
        )
    latest = usable[-1]["trade_date"].isoformat() if usable else None
    if latest is not None and latest != as_of_date.isoformat():
        warnings.append(
            f"Requested as_of_date is {as_of_date.isoformat()}, while the latest trade "
            f"observation is {latest}; the signal is dated {latest}."
        )
    quality_status = "ready"
    if not usable:
        quality_status = "insufficient"
    elif invalid_count or duplicate_count:
        quality_status = "degraded"
    return usable, {
        "status": quality_status,
        "input_row_count": len(input_rows),
        "usable_row_count": len(usable),
        "invalid_row_count": invalid_count,
        "duplicate_date_count": duplicate_count,
        "latest_trade_date": latest,
        "warnings": warnings,
    }


def _normalise_nav_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_of_date: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalised: dict[date, dict[str, Any]] = {}
    invalid_count = 0
    duplicate_count = 0
    future_count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            invalid_count += 1
            continue
        row_date = _parse_date(row.get("trade_date") or row.get("date"))
        nav = _finite_float(row.get("nav"))
        if row_date is None or nav is None or nav <= 0:
            invalid_count += 1
            continue
        if row_date > as_of_date:
            future_count += 1
            continue
        if row_date in normalised:
            duplicate_count += 1
        normalised[row_date] = {
            "trade_date": row_date,
            "nav": nav,
            "temperature": _finite_float(
                row.get("temperature")
                if "temperature" in row
                else row.get("resume_temperature")
            ),
        }
    usable = [normalised[key] for key in sorted(normalised)]
    warnings: list[str] = []
    if invalid_count:
        warnings.append(f"Dropped {invalid_count} invalid portfolio NAV row(s).")
    if duplicate_count:
        warnings.append(
            f"Found {duplicate_count} duplicate NAV date(s); retained the last supplied row."
        )
    if future_count:
        warnings.append(f"Ignored {future_count} NAV row(s) after requested as_of_date.")
    status = "ready" if usable and not invalid_count and not duplicate_count else "degraded"
    if not usable:
        status = "insufficient"
    return usable, {"status": status, "warnings": warnings}


def _validated_config(override: Mapping[str, Any] | None) -> dict[str, float | int]:
    config = {**DEFAULT_CONFIG, **dict(override or {})}
    positive_int_keys = {
        "high_window",
        "thrust_window",
        "atr_window",
        "exit_ma_window",
        "exit_below_days",
        "fast_drawdown_window",
        "cooldown_days",
        "ramp_days",
    }
    for key in positive_int_keys:
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or value <= 0:
            raise ValueError(f"{key} must be a positive integer")
        config[key] = int(value)
    for key in set(DEFAULT_CONFIG) - positive_int_keys:
        value = _finite_float(config.get(key))
        if value is None:
            raise ValueError(f"{key} must be a finite number")
        config[key] = value
    if int(config["high_window"]) > int(config["exit_ma_window"]):
        raise ValueError("high_window cannot exceed exit_ma_window")
    if int(config["atr_window"]) > int(config["exit_ma_window"]):
        raise ValueError("atr_window cannot exceed exit_ma_window")
    if int(config["thrust_window"]) >= int(config["exit_ma_window"]):
        raise ValueError("thrust_window must be smaller than exit_ma_window")
    return config


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _nonnegative_int(value: Any) -> int | None:
    numeric = _finite_float(value)
    if numeric is None or numeric < 0 or int(numeric) != numeric:
        return None
    return int(numeric)


def _round_metric(value: float) -> float:
    return round(float(value), 8)


def _optional_rounded_metric(value: Any) -> float | None:
    numeric = _finite_float(value)
    return _round_metric(numeric) if numeric is not None else None


def _round_weight(value: float) -> float:
    return round(float(value), 6)


def _dedupe(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
