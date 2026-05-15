from __future__ import annotations

from typing import Any, cast

import pytest

from tests.helpers import load_module


def _service_module():
    return load_module(
        "backend.app.services.livermore_signal_confluence_service",
        "backend/app/services/livermore_signal_confluence_service.py",
    )


def _build_livermore_signal_confluence(
    *,
    as_of_date: str,
    livermore_payload: dict[str, object],
    macro_payload: dict[str, object],
    adversarial_payload: dict[str, object] | None = None,
    backtest_window_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    module = _service_module()
    return cast(
        dict[str, object],
        module.build_livermore_signal_confluence(
            as_of_date=as_of_date,
            livermore_payload=livermore_payload,
            macro_payload=macro_payload,
            adversarial_payload=adversarial_payload,
            backtest_window_summary=backtest_window_summary,
        ),
    )


def test_build_livermore_signal_confluence_allows_observation_entries_when_gate_is_hot_and_macro_supportive() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "HOT",
                "exposure": 0.75,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000001.SZ",
                        "stock_name": "Alpha",
                        "breakout_level": 21.8,
                        "close": 21.9,
                        "ema10": 20.6,
                    }
                ]
            },
            "risk_exit": {
                "watch_items": [
                    {
                        "stock_code": "000777.SZ",
                        "stock_name": "Watch Alpha",
                        "latest_close": 19.8,
                        "latest_ema10": 20.1,
                    }
                ]
            },
        },
        macro_payload={
            "environment_score": {
                "composite_score": -0.45,
            }
        },
    )

    assert result["as_of_date"] == "2026-05-02"
    assert result["position_size_hint"] == pytest.approx(0.75)
    assert result["disclaimer"] == (
        "Observation-only output. This service does not generate trading instructions."
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "supportive"
    assert macro_context["composite_score"] == pytest.approx(-0.45)
    assert macro_context["multiplier"] == pytest.approx(1.0)

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "HOT"
    assert strategy_context["market_gate_exposure"] == pytest.approx(0.75)
    assert strategy_context["allows_new_entry_observations"] is True

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert len(entry_observations) == 1
    assert entry_observations[0] == {
        "stock_code": "000001.SZ",
        "stock_name": "Alpha",
        "action": "observe_entry_setup",
        "trigger_price": 21.8,
        "current_price": 21.9,
        "invalidation_reference_price": 20.6,
        "evidence": [
            "候选触发价来自 Livermore breakout_level。",
            "失效参考价来自候选股 EMA10。",
        ],
    }

    exit_observations = cast(list[dict[str, Any]], result["exit_observations"])
    assert exit_observations == [
        {
            "stock_code": "000777.SZ",
            "stock_name": "Watch Alpha",
            "action": "observe_exit_watch",
            "current_price": 19.8,
            "exit_watch_price": 20.1,
            "triggered": False,
            "evidence": ["退出观察价来自 Livermore EMA10。"],
        }
    ]
    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["exit_gate"] == "watch"

    diagnostics = cast(list[str], result["diagnostics"])
    assert diagnostics[-1] == (
        "Observation-only output. This service does not generate trading instructions."
    )


def test_build_livermore_signal_confluence_keeps_candidate_price_facts_visible_but_observe_only_when_macro_is_restrictive() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "OVERHEAT",
                "exposure": 1.0,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000002.SZ",
                        "stock_name": "Beta",
                        "breakout_level": 12.4,
                        "close": 12.1,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": 0.4,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "restrictive"
    assert result["position_size_hint"] == pytest.approx(0.0)

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["allows_new_entry_observations"] is False

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations == [
        {
            "stock_code": "000002.SZ",
            "stock_name": "Beta",
            "action": "observe_only",
            "trigger_price": 12.4,
            "current_price": 12.1,
            "invalidation_reference_price": None,
            "evidence": ["候选触发价来自 Livermore breakout_level。"],
        }
    ]
    assert "buy" not in str(entry_observations[0]).lower()
    diagnostics = cast(list[str], result["diagnostics"])
    assert "Stock 000002.SZ is missing EMA10; invalidation reference price is unavailable." in diagnostics


def test_build_livermore_signal_confluence_overheat_stays_observe_only_even_when_macro_is_supportive() -> None:
    """OVERHEAT 历史回测 win_5d=41.1% / avg=-0.09%，任何 macro 下都不放行新观察入场。"""
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "OVERHEAT",
                "exposure": 1.0,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000003.SZ",
                        "stock_name": "Gamma",
                        "breakout_level": 33.0,
                        "close": 33.4,
                        "ema10": 31.2,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.5,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "supportive"

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "OVERHEAT"
    assert strategy_context["allows_new_entry_observations"] is False

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_only"


def test_build_livermore_signal_confluence_uses_observe_only_when_adversarial_gate_blocks() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "HOT",
                "exposure": 0.6,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000006.SZ",
                        "stock_name": "Zeta",
                        "breakout_level": 18.2,
                        "close": 18.5,
                        "ema10": 17.8,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.4,
            }
        },
        adversarial_payload={
            "status": "ok",
            "risk_gate": "block",
            "diagnostics": ["Crowding reversal risk is elevated."],
        },
    )

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["allows_new_entry_observations"] is True

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_only"

    adversarial_context = cast(dict[str, Any], result["adversarial_context"])
    assert adversarial_context["status"] == "ok"
    assert adversarial_context["risk_gate"] == "block"
    assert adversarial_context["mode"] == "macro_adversarial_crowding"
    assert adversarial_context["position_scale"] is None
    assert adversarial_context["blocks_new_entry_observations"] is True

    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["status"] == "blocked_by_adversarial"
    assert closed_loop_state["entry_gate"] == "blocked"
    assert closed_loop_state["lineage_status"] == "complete"
    assert closed_loop_state["entry_observation_action"] == "observe_only"

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Adversarial risk gate is blocking new entry observations; candidate entries stay observe_only." in diagnostics


def test_build_livermore_signal_confluence_keeps_entries_visible_when_adversarial_signal_is_missing() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000007.SZ",
                        "stock_name": "Eta",
                        "breakout_level": 16.2,
                        "close": 16.4,
                        "ema10": 15.7,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.1,
            }
        },
    )

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_entry_setup"

    adversarial_context = cast(dict[str, Any], result["adversarial_context"])
    assert adversarial_context["status"] == "missing"
    assert adversarial_context["risk_gate"] == "missing"
    assert adversarial_context["blocks_new_entry_observations"] is False

    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["status"] == "degraded_missing_adversarial"
    assert closed_loop_state["entry_gate"] == "open"
    assert closed_loop_state["replay_status"] == {
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
    assert closed_loop_state["lineage_status"] == "missing"
    assert closed_loop_state["entry_observation_action"] == "observe_entry_setup"

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Macro adversarial signal is missing; no adversarial gate is applied." in diagnostics


def test_build_livermore_signal_confluence_reports_missing_inputs_and_stays_observation_only() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={},
        macro_payload={},
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "unknown"
    assert macro_context["composite_score"] is None
    assert macro_context["multiplier"] == pytest.approx(0.0)

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "UNKNOWN"
    assert strategy_context["market_gate_exposure"] == pytest.approx(0.0)
    assert strategy_context["allows_new_entry_observations"] is False

    assert result["position_size_hint"] == pytest.approx(0.0)
    assert result["entry_observations"] == []
    assert result["exit_observations"] == []

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Missing macro composite score; macro context is unknown." in diagnostics
    assert "Missing Livermore market gate; entry observations are blocked." in diagnostics
    assert "No stock candidates available for observation." in diagnostics
    assert "No risk exit watch items or triggered exit items available." in diagnostics
    assert diagnostics[-1] == (
        "Observation-only output. This service does not generate trading instructions."
    )


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), float("-inf"), "nan"])
def test_build_livermore_signal_confluence_rejects_non_finite_macro_scores(bad_score: object) -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000005.SZ",
                        "stock_name": "Epsilon",
                        "breakout_level": 15.2,
                        "close": 15.0,
                        "ema10": 14.7,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": bad_score,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "unknown"
    assert macro_context["composite_score"] is None
    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["allows_new_entry_observations"] is False
    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_only"
    diagnostics = cast(list[str], result["diagnostics"])
    assert "Missing macro composite score; macro context is unknown." in diagnostics


def test_build_livermore_signal_confluence_falls_back_to_triggered_exit_items_when_watch_items_are_absent() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "risk_exit": {
                "items": [
                    {
                        "stock_code": "000003.SZ",
                        "stock_name": "Gamma",
                        "latest_close": 9.1,
                        "latest_ema10": 9.8,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": 0.0,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "neutral"
    assert result["position_size_hint"] == pytest.approx(0.25)

    exit_observations = cast(list[dict[str, Any]], result["exit_observations"])
    assert exit_observations == [
        {
            "stock_code": "000003.SZ",
            "stock_name": "Gamma",
            "action": "exit_triggered",
            "current_price": 9.1,
            "exit_watch_price": 9.8,
            "triggered": True,
            "evidence": ["退出观察价来自 Livermore EMA10。"],
        }
    ]
    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["exit_gate"] == "triggered"


def test_build_livermore_signal_confluence_does_not_invent_exit_watch_evidence_when_ema10_is_missing() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "risk_exit": {
                "watch_items": [
                    {
                        "stock_code": "000004.SZ",
                        "stock_name": "Delta",
                        "latest_close": 10.1,
                        "triggered": False,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": 0.0,
            }
        },
    )

    exit_observations = cast(list[dict[str, Any]], result["exit_observations"])
    assert exit_observations == [
        {
            "stock_code": "000004.SZ",
            "stock_name": "Delta",
            "action": "observe_exit_watch",
            "current_price": 10.1,
            "exit_watch_price": None,
            "triggered": False,
            "evidence": [],
        }
    ]
    diagnostics = cast(list[str], result["diagnostics"])
    assert "Stock 000004.SZ is missing EMA10; exit watch price is unavailable." in diagnostics


def test_build_livermore_signal_confluence_projects_backtest_window_summary_into_closed_loop_replay_status() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-08",
        livermore_payload={
            "market_gate": {
                "state": "HOT",
                "exposure": 0.6,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000006.SZ",
                        "stock_name": "Zeta",
                        "breakout_level": 18.2,
                        "close": 18.5,
                        "ema10": 17.8,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.4,
            }
        },
        backtest_window_summary={
            "status": "partial",
            "snapshot_from": "2026-04-30",
            "snapshot_to": "2026-05-08",
            "replay_dates_total": 4,
            "replay_dates_completed": 1,
            "replay_dates_pending": 1,
            "replay_dates_unsupported": 1,
            "replay_dates_proxy_only": 1,
            "completed_rows": 0,
            "pending_rows": 1,
            "unsupported_rows": 0,
            "proxy_only_rows": 1,
            "excluded_from_completed_stats_dates": ["2026-04-30", "2026-05-07", "2026-05-08"],
            "included_completed_stats_dates": ["2026-05-06"],
            "date_reasons": [
                {
                    "trade_date": "2026-04-30",
                    "status": "unsupported",
                    "reason_code": "missing_daily_limit_flags",
                    "message": "daily_limit_flags absent; Livermore strategy replay unsupported for 2026-04-30.",
                    "affects_completed_stats": False,
                    "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
                },
                {
                    "trade_date": "2026-05-06",
                    "status": "completed",
                    "reason_code": "no_strategy_signals",
                    "message": "Full replay coverage produced no Livermore strategy signal rows for 2026-05-06.",
                    "affects_completed_stats": True,
                    "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
                },
                {
                    "trade_date": "2026-05-07",
                    "status": "proxy_only",
                    "reason_code": "proxy_theme_only",
                    "message": "Theme breakout replay for 2026-05-07 relies on proxy-only theme evidence.",
                    "affects_completed_stats": False,
                    "signal_kinds": ["theme_breakout"],
                },
                {
                    "trade_date": "2026-05-08",
                    "status": "pending",
                    "reason_code": "forward_returns_pending",
                    "message": "Forward return bars are not available yet; exclude 2026-05-08 from completed forward-return statistics.",
                    "affects_completed_stats": False,
                    "signal_kinds": ["stock_candidate"],
                },
            ],
        },
    )

    replay_status = cast(dict[str, Any], cast(dict[str, Any], result["closed_loop_state"])["replay_status"])
    assert replay_status == {
        "window_status": "partial",
        "has_decision_usable_completed_stats": True,
        "completed_dates": 1,
        "pending_dates": 1,
        "unsupported_dates": 1,
        "proxy_only_dates": 1,
        "completed_candidate_rows": 0,
        "pending_candidate_rows": 1,
        "unsupported_candidate_rows": 0,
        "proxy_only_candidate_rows": 1,
        "included_completed_stats_dates": ["2026-05-06"],
        "blocked_dates": [
                {
                    "trade_date": "2026-04-30",
                    "status": "unsupported",
                    "reason_code": "missing_daily_limit_flags",
                    "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
                },
            {
                "trade_date": "2026-05-07",
                "status": "proxy_only",
                "reason_code": "proxy_theme_only",
                "signal_kinds": ["theme_breakout"],
            },
            {
                "trade_date": "2026-05-08",
                "status": "pending",
                "reason_code": "forward_returns_pending",
                "signal_kinds": ["stock_candidate"],
            },
        ],
        "completed_zero_signal_dates": ["2026-05-06"],
    }


def test_build_livermore_replay_status_accepts_private_included_completed_dates_key() -> None:
    module = _service_module()

    replay_status = module.build_livermore_replay_status(
        {
            "status": "valid",
            "replay_dates_completed": 1,
            "replay_dates_pending": 0,
            "replay_dates_unsupported": 0,
            "replay_dates_proxy_only": 0,
            "completed_rows": 1,
            "pending_rows": 0,
            "unsupported_rows": 0,
            "proxy_only_rows": 0,
            "_included_completed_stats_dates": ["2026-05-06"],
            "date_reasons": [],
        }
    )

    assert replay_status["included_completed_stats_dates"] == ["2026-05-06"]
    assert replay_status["has_decision_usable_completed_stats"] is True
