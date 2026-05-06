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
) -> dict[str, object]:
    module = _service_module()
    return cast(
        dict[str, object],
        module.build_livermore_signal_confluence(
            as_of_date=as_of_date,
            livermore_payload=livermore_payload,
            macro_payload=macro_payload,
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
