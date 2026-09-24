"""宏观主信号契约：风险优先规则不得退回按原始分数跨量纲排序。

Crisis 是 z-score（2 已是高风险），A股踩踏是 0-100 分，流动性等方向卡是固定
离散状态分。三者不可直接比较，因此主信号由后端按风险优先规则显式声明，
前端只按 key 取卡。
"""
from __future__ import annotations

import pytest

from backend.app.services.macro_toolkit_analysis_service import (
    PRIMARY_SIGNAL_RULE_VERSION,
    select_primary_signal,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _card(key: str, tone: str, score: float | None) -> dict[str, object]:
    return {"key": key, "title": key, "stance": "", "tone": tone, "score": score, "evidence": []}


def _crisis_capability(score: float) -> dict[str, object]:
    return {"key": "crisis_score_cn", "score": score, "result": {"crisis_score": score}}


def _direction_cards() -> list[dict[str, object]]:
    return [
        _card("liquidity", "positive", 78),
        _card("risk_appetite", "neutral", 52),
        _card("credit", "neutral", 55),
        _card("outputs", "positive", 100),
    ]


def test_high_risk_crisis_beats_higher_scoring_liquidity_card() -> None:
    """Crisis 2.5（高风险）必须压过流动性 78，尽管原始分数更低。"""
    cards = [*_direction_cards(), _card("crisis_score_cn", "negative", 2.5)]

    primary = select_primary_signal(
        cards,
        a_share_risk={"risk_level": "green", "risk_score": 27},
        capability_results=[_crisis_capability(2.5)],
        capabilities_deferred=False,
    )

    assert primary["key"] == "crisis_score_cn"
    assert primary["selection_status"] == "selected"
    assert primary["reason_code"] == "risk_gate_crisis_score"
    assert primary["rule_version"] == PRIMARY_SIGNAL_RULE_VERSION


def test_red_a_share_risk_wins_when_crisis_is_calm() -> None:
    cards = [*_direction_cards(), _card("a_share_stampede_risk", "negative", 82)]

    primary = select_primary_signal(
        cards,
        a_share_risk={"risk_level": "red", "risk_score": 82},
        capability_results=[_crisis_capability(-0.1)],
        capabilities_deferred=False,
    )

    assert primary["key"] == "a_share_stampede_risk"
    assert primary["reason_code"] == "risk_gate_a_share_stampede"


def test_crisis_takes_precedence_over_a_share_at_the_same_severity_tier() -> None:
    """同为 3 档时取 Crisis：系统性风险优先于单市场踩踏。"""
    primary = select_primary_signal(
        [*_direction_cards(), _card("crisis_score_cn", "negative", 2.1)],
        a_share_risk={"risk_level": "orange", "risk_score": 64},
        capability_results=[_crisis_capability(2.1)],
        capabilities_deferred=False,
    )

    assert primary["key"] == "crisis_score_cn"


def test_yellow_a_share_and_alert_crisis_do_not_trigger_the_risk_gate() -> None:
    """警惕档（1<=score<2）和 yellow 档未达闸门，回到方向信号。"""
    primary = select_primary_signal(
        [*_direction_cards(), _card("crisis_score_cn", "neutral", 1.4)],
        a_share_risk={"risk_level": "yellow", "risk_score": 48},
        capability_results=[_crisis_capability(1.4)],
        capabilities_deferred=False,
    )

    assert primary["key"] == "liquidity"
    assert primary["reason_code"] == "strongest_direction_signal"


def test_strongest_direction_signal_uses_deviation_from_each_neutral_baseline() -> None:
    """信用 38（偏离 17）强于流动性 55（偏离 0）。"""
    cards = [
        _card("liquidity", "neutral", 55),
        _card("risk_appetite", "negative", 35),
        _card("credit", "negative", 38),
    ]

    primary = select_primary_signal(
        cards,
        a_share_risk={"risk_level": "green", "risk_score": 20},
        capability_results=[_crisis_capability(0.2)],
        capabilities_deferred=False,
    )

    assert primary["key"] == "credit"


def test_core_scope_defers_instead_of_promoting_a_direction_card() -> None:
    """core 首屏没有 Crisis / A股候选，不能让方向卡临时冒充主信号。"""
    primary = select_primary_signal(
        _direction_cards(),
        a_share_risk=None,
        capability_results=[],
        capabilities_deferred=True,
    )

    assert primary["key"] is None
    assert primary["selection_status"] == "deferred"
    assert primary["reason_code"] == "core_scope_risk_candidates_deferred"


def test_missing_direction_cards_fail_closed_without_falling_back_to_outputs() -> None:
    primary = select_primary_signal(
        [
            _card("liquidity", "missing", None),
            _card("risk_appetite", "missing", None),
            _card("credit", "missing", None),
            _card("outputs", "positive", 100),
        ],
        a_share_risk={"status": "unavailable"},
        capability_results=[],
        capabilities_deferred=False,
    )

    assert primary["key"] is None
    assert primary["selection_status"] == "unavailable"
    assert primary["reason_code"] == "no_eligible_signal"


def test_selected_key_always_matches_a_returned_non_outputs_card() -> None:
    cards = [*_direction_cards(), _card("crisis_score_cn", "negative", 3.4)]

    for a_share_level, crisis_score in (("red", 3.4), ("green", 0.1), ("orange", 1.0)):
        primary = select_primary_signal(
            cards,
            a_share_risk={"risk_level": a_share_level, "risk_score": 50},
            capability_results=[_crisis_capability(crisis_score)],
            capabilities_deferred=False,
        )
        if primary["key"] is None:
            continue
        assert primary["key"] != "outputs"
        assert any(card["key"] == primary["key"] for card in cards)
