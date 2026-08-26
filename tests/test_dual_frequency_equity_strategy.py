from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.core_finance.macro.dual_frequency_equity import (
    FORMULA_VERSION,
    build_dual_frequency_equity_snapshot,
)


def _market_rows(
    closes: list[float],
    *,
    amounts: list[float] | None = None,
    start: date = date(2026, 1, 1),
) -> list[dict[str, object]]:
    values = amounts or [100.0] * len(closes)
    return [
        {
            "trade_date": (start + timedelta(days=index)).isoformat(),
            "close": close,
            "amount": values[index],
        }
        for index, close in enumerate(closes)
    ]


def _attack_market_rows(count: int = 61) -> list[dict[str, object]]:
    closes = [100.0] * count
    amounts = [100.0] * count
    closes[60] = 106.0
    amounts[60] = 200.0
    for index in range(61, count):
        closes[index] = 106.0
    return _market_rows(closes, amounts=amounts)


def _nav_rows(
    market_rows: list[dict[str, object]],
    navs: list[float],
    *,
    final_temperature: float | None = None,
) -> list[dict[str, object]]:
    selected = market_rows[-len(navs) :]
    result: list[dict[str, object]] = []
    for index, (market_row, nav) in enumerate(zip(selected, navs, strict=True)):
        row: dict[str, object] = {
            "trade_date": market_row["trade_date"],
            "nav": nav,
        }
        if index == len(navs) - 1 and final_temperature is not None:
            row["temperature"] = final_temperature
        result.append(row)
    return result


def test_insufficient_history_withholds_fast_and_final_targets() -> None:
    rows = _market_rows([100.0] * 60)
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.7,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )

    assert payload["boundary"] == "observation_only"
    assert payload["execution_enabled"] is False
    assert payload["formula_version"] == FORMULA_VERSION
    assert payload["data_status"]["status"] == "insufficient"
    assert payload["fast"] == {
        "status": "insufficient",
        "state": None,
        "multiplier": None,
        "signal_date": str(rows[-1]["trade_date"]),
        "minimum_required_rows": 61,
        "available_rows": 60,
        "last_transition": None,
        "latest_metrics": None,
    }
    assert payload["pre_survival_target_total_weight"] is None
    assert payload["final_target_total_weight"] is None


def test_fast_layer_enters_attack_on_current_inclusive_high_and_amount_ratio() -> None:
    rows = _attack_market_rows()
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )

    fast = payload["fast"]
    assert fast["status"] == "ready"
    assert fast["state"] == "attack"
    assert fast["multiplier"] == 1.0
    assert fast["signal_date"] == as_of.isoformat()
    assert fast["latest_metrics"]["amount_ratio_20"] == pytest.approx(200 / 105)
    assert fast["latest_metrics"]["high_20"] == 106.0
    assert fast["last_transition"]["reason"] == "high_amount_breakout"
    assert payload["pre_survival_target_total_weight"] == 0.8
    assert payload["survival"]["status"] == "not_evaluated"
    assert payload["data_status"]["status"] == "degraded"
    assert payload["final_target_total_weight"] is None


def test_bounded_history_without_authoritative_fast_state_is_insufficient() -> None:
    rows = _market_rows(
        [
            100.0 if index < 61 else 101.0 + (index - 61) * 0.001
            for index in range(400)
        ],
        amounts=[10_000.0 if index == 61 else 100.0 for index in range(400)],
        start=date(2025, 1, 1),
    )
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    complete = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )
    bounded = build_dual_frequency_equity_snapshot(
        daily_rows=rows[-260:],
        slow_cap=0.8,
        as_of_date=as_of,
    )

    assert complete["fast"]["status"] == "ready"
    assert complete["fast"]["state"] == "attack"
    assert complete["fast"]["multiplier"] == 1.0
    assert bounded["fast"]["status"] == "insufficient"
    assert bounded["fast"]["state"] is None
    assert bounded["fast"]["multiplier"] is None
    assert bounded["fast"]["reason"] == "bounded_history_without_authoritative_fast_state"
    assert bounded["pre_survival_target_total_weight"] is None


def test_date_aligned_authoritative_fast_state_resolves_bounded_history() -> None:
    rows = _market_rows([100.0] * 80)
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_state={
            "authoritative": True,
            "signal_date": as_of.isoformat(),
            "state": "attack",
            "highest_close_since_attack": 100.0,
        },
    )

    assert payload["fast"]["status"] == "ready"
    assert payload["fast"]["source"] == "portfolio_fast_state"
    assert payload["fast"]["state"] == "attack"
    assert payload["fast"]["multiplier"] == 1.0
    assert payload["fast"]["highest_close_since_attack"] == 100.0
    assert payload["pre_survival_target_total_weight"] == 0.8


def test_authoritative_attack_state_rejects_high_below_latest_close() -> None:
    rows = _market_rows([100.0] * 79 + [101.0])
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_state={
            "authoritative": True,
            "signal_date": as_of.isoformat(),
            "state": "attack",
            "highest_close_since_attack": 100.0,
        },
    )

    assert payload["fast"]["status"] == "insufficient"
    assert (
        payload["fast"]["reason"]
        == "attack_state_highest_close_below_latest_close"
    )
    assert payload["pre_survival_target_total_weight"] is None


def test_fast_layer_enters_attack_on_five_day_thrust_without_twenty_day_high() -> None:
    closes = [100.0] * 61
    amounts = [100.0] * 61
    closes[45] = 120.0
    closes[60] = 106.0
    amounts[60] = 150.0
    rows = _market_rows(closes, amounts=amounts)
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )

    metrics = payload["fast"]["latest_metrics"]
    assert metrics["high_20"] == 120.0
    assert metrics["close"] == 106.0
    assert metrics["amount_ratio_20"] < 1.5
    assert metrics["amount_ratio_20"] >= 1.3
    assert metrics["return_5"] == 0.06
    assert payload["fast"]["state"] == "attack"
    assert payload["fast"]["last_transition"]["reason"] == "five_day_thrust"


def test_atr_proxy_uses_absolute_positive_and_negative_close_returns() -> None:
    closes = [100.0]
    for index in range(1, 61):
        closes.append(closes[-1] * (1.01 if index % 2 else 0.99))
    rows = _market_rows(closes)
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.7,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )

    expected = (
        sum(
            abs(closes[index] / closes[index - 1] - 1.0)
            for index in range(41, 61)
        )
        / 20
        * closes[-1]
    )
    atr_proxy = payload["fast"]["latest_metrics"]["atr_proxy_20"]
    assert atr_proxy == pytest.approx(expected, abs=1e-8)
    assert atr_proxy > 0.0
    assert "abs(close.pct_change())" in payload["methodology"]["atr_proxy"]


def test_fast_layer_exits_after_two_consecutive_closes_below_ma60() -> None:
    rows = _attack_market_rows(63)
    rows[61]["close"] = 99.0
    rows[62]["close"] = 99.0
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        config={"atr_multiple": 1000.0},
    )

    assert payload["fast"]["state"] == "defense"
    assert payload["fast"]["multiplier"] == 0.4
    assert payload["fast"]["last_transition"]["reason"] == "two_closes_below_ma60"
    assert payload["pre_survival_target_total_weight"] == 0.32


def test_fast_layer_exits_on_chandelier_before_two_closes_below_ma60() -> None:
    rows = _attack_market_rows(62)
    rows[61]["close"] = 100.0
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )

    assert payload["fast"]["state"] == "defense"
    assert payload["fast"]["last_transition"]["date"] == str(rows[61]["trade_date"])
    assert payload["fast"]["last_transition"]["reason"] == "chandelier_exit"
    assert payload["fast"]["latest_metrics"]["consecutive_closes_below_ma60"] == 0


def test_unconfirmed_nav_history_cannot_authorize_a_final_target() -> None:
    market_rows = _attack_market_rows()
    nav_rows = _nav_rows(market_rows, [0.8] * 6)
    as_of = date.fromisoformat(str(market_rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=market_rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=nav_rows,
    )

    assert payload["pre_survival_target_total_weight"] == 0.8
    assert payload["survival"]["status"] == "insufficient"
    assert (
        payload["survival"]["reason"]
        == "nav_history_not_confirmed_authoritative_complete"
    )
    assert payload["final_target_total_weight"] is None
    assert payload["provenance"]["nav_history_authoritative_complete"] is False
    assert any("complete from strategy inception" in warning for warning in payload["warnings"])


def test_explicitly_complete_authoritative_nav_history_can_authorize_final_target() -> None:
    market_rows = _attack_market_rows()
    nav_rows = _nav_rows(market_rows, [0.8] * 6)
    as_of = date.fromisoformat(str(market_rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=market_rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=nav_rows,
        nav_history_authoritative_complete=True,
    )

    assert payload["survival"]["status"] == "ready"
    assert payload["survival"]["state"] == "normal"
    assert payload["survival"]["multiplier"] == 1.0
    assert payload["final_target_total_weight"] == 0.8
    assert payload["provenance"]["nav_history_authoritative_complete"] is True


def test_nav_five_day_drawdown_halves_the_final_target() -> None:
    market_rows = _attack_market_rows(67)
    nav_rows = _nav_rows(market_rows, [1.0] * 6 + [0.89])
    as_of = date.fromisoformat(str(market_rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=market_rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=nav_rows,
        nav_history_authoritative_complete=True,
    )

    assert payload["survival"]["status"] == "ready"
    assert payload["survival"]["state"] == "halved"
    assert payload["survival"]["multiplier"] == 0.5
    assert payload["survival"]["current_drawdown"] == -0.11
    assert payload["survival"]["five_day_drawdown"] == -0.11
    assert payload["final_target_total_weight"] == 0.4
    assert payload["data_status"]["status"] == "ready"
    assert any(event["event"] == "halve" for event in payload["events"])


def test_kill_stays_at_zero_after_cooldown_when_resume_temperature_is_missing() -> None:
    market_rows = _attack_market_rows(67)
    nav_rows = _nav_rows(market_rows, [1.0] * 6 + [0.69] * 61)
    as_of = date.fromisoformat(str(market_rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=market_rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=nav_rows,
        nav_history_authoritative_complete=True,
    )

    survival = payload["survival"]
    assert survival["status"] == "ready"
    assert survival["state"] == "killed"
    assert survival["multiplier"] == 0.0
    assert survival["cooldown_remaining"] == 0
    assert payload["final_target_total_weight"] == 0.0
    assert any("resume temperature was unavailable" in warning for warning in payload["warnings"])


def test_killed_state_resumes_into_twenty_day_half_weight_ramp() -> None:
    market_rows = _attack_market_rows(67)
    nav_rows = _nav_rows(
        market_rows,
        [1.0] * 6 + [0.69] * 61,
        final_temperature=60.0,
    )
    as_of = date.fromisoformat(str(market_rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=market_rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=nav_rows,
        nav_history_authoritative_complete=True,
    )

    survival = payload["survival"]
    assert survival["state"] == "ramp"
    assert survival["multiplier"] == 0.5
    assert survival["killed"] is False
    assert survival["ramp_remaining"] == 19
    assert payload["final_target_total_weight"] == 0.4
    assert payload["events"][-1]["event"] == "resume"


def test_out_of_range_slow_cap_is_not_clipped_or_inferred() -> None:
    rows = _attack_market_rows()
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=1.2,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
    )

    assert payload["slow"]["status"] == "insufficient"
    assert payload["slow"]["cap"] is None
    assert payload["data_status"]["status"] == "insufficient"
    assert payload["pre_survival_target_total_weight"] is None
    assert payload["final_target_total_weight"] is None
    assert any("did not clip" in warning for warning in payload["warnings"])


def test_request_date_and_actual_signal_date_are_not_conflated() -> None:
    rows = _attack_market_rows()
    latest_trade_date = date.fromisoformat(str(rows[-1]["trade_date"]))
    requested_date = latest_trade_date + timedelta(days=3)

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=requested_date,
        fast_history_authoritative_complete=True,
    )

    assert payload["as_of_date"] == requested_date.isoformat()
    assert payload["fast"]["signal_date"] == latest_trade_date.isoformat()
    assert payload["data_status"]["latest_trade_date"] == latest_trade_date.isoformat()
    assert payload["data_status"]["as_of_alignment"] == "prior_observation"
    assert payload["provenance"]["signal_date"] == latest_trade_date.isoformat()
    assert any("the signal is dated" in warning for warning in payload["warnings"])


def test_date_aligned_authoritative_survival_state_allows_final_target() -> None:
    rows = _attack_market_rows()
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=_nav_rows(rows, [0.8] * 6),
        survival_state={
            "authoritative": True,
            "signal_date": as_of.isoformat(),
            "killed": False,
            "halved": True,
            "cooldown_remaining": 0,
            "ramp_remaining": 0,
            "current_drawdown": -0.12,
            "five_day_drawdown": -0.03,
        },
    )

    assert payload["survival"]["status"] == "ready"
    assert payload["survival"]["source"] == "portfolio_survival_state"
    assert payload["survival"]["state"] == "halved"
    assert payload["final_target_total_weight"] == 0.4


def test_valid_authoritative_state_precedes_stale_complete_nav_history() -> None:
    rows = _attack_market_rows()
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))
    stale_nav_rows = _nav_rows(rows[:-1], [0.8] * 6)

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=stale_nav_rows,
        nav_history_authoritative_complete=True,
        survival_state={
            "authoritative": True,
            "signal_date": as_of.isoformat(),
            "killed": False,
            "halved": True,
            "cooldown_remaining": 0,
            "ramp_remaining": 0,
        },
    )

    assert payload["survival"]["status"] == "ready"
    assert payload["survival"]["source"] == "portfolio_survival_state"
    assert payload["survival"]["state"] == "halved"
    assert payload["final_target_total_weight"] == 0.4


def test_valid_complete_nav_history_follows_insufficient_authoritative_state() -> None:
    rows = _attack_market_rows()
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))
    nav_rows = _nav_rows(rows, [0.8] * 6)

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=nav_rows,
        nav_history_authoritative_complete=True,
        survival_state={
            "authoritative": True,
            "signal_date": (as_of - timedelta(days=1)).isoformat(),
            "killed": False,
            "halved": True,
            "cooldown_remaining": 0,
            "ramp_remaining": 0,
        },
    )

    assert payload["survival"]["status"] == "ready"
    assert payload["survival"]["source"] == "portfolio_nav_history"
    assert payload["survival"]["state"] == "normal"
    assert payload["final_target_total_weight"] == 0.8
    assert any("state date does not match" in warning for warning in payload["warnings"])
    assert any("NAV history was used instead" in warning for warning in payload["warnings"])


def test_two_insufficient_survival_inputs_report_combined_reason_and_warnings() -> None:
    rows = _attack_market_rows()
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))
    stale_nav_rows = _nav_rows(rows[:-1], [0.8] * 6)

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.8,
        as_of_date=as_of,
        fast_history_authoritative_complete=True,
        nav_rows=stale_nav_rows,
        nav_history_authoritative_complete=True,
        survival_state={
            "authoritative": True,
            "signal_date": (as_of - timedelta(days=1)).isoformat(),
            "killed": False,
            "halved": True,
            "cooldown_remaining": 0,
            "ramp_remaining": 0,
        },
    )

    assert payload["survival"]["status"] == "insufficient"
    assert payload["survival"]["source"] == "portfolio_survival_inputs"
    assert (
        payload["survival"]["reason"]
        == "authoritative_state_and_nav_history_insufficient"
    )
    assert payload["final_target_total_weight"] is None
    assert any("state date does not match" in warning for warning in payload["warnings"])
    assert any("NAV date does not match" in warning for warning in payload["warnings"])
    assert any("Neither the authoritative" in warning for warning in payload["warnings"])


def test_provenance_source_strategy_is_machine_independent_identifier() -> None:
    rows = _market_rows([100.0] * 60)
    as_of = date.fromisoformat(str(rows[-1]["trade_date"]))

    payload = build_dual_frequency_equity_snapshot(
        daily_rows=rows,
        slow_cap=0.7,
        as_of_date=as_of,
    )

    assert payload["provenance"]["source_strategy"] == "desktop:a_share_dual_freq_v6.py"
