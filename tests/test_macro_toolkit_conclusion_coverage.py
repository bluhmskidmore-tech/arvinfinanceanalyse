"""Incomplete directional evidence must not imply a market stance."""

from __future__ import annotations

import pytest

from backend.app.services.macro_toolkit_route_support import _analysis_conclusion

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


@pytest.mark.parametrize(
    ("tones", "valid_count", "missing_keys"),
    [
        (("positive", "missing", "missing"), 1, ["credit", "risk_appetite"]),
        (("missing", "missing", "missing"), 0, ["credit", "liquidity", "risk_appetite"]),
        (("negative", "negative", "missing"), 2, ["credit"]),
        (("neutral", None, "neutral"), 2, ["risk_appetite"]),
        (("neutral", "unknown", "neutral"), 2, ["risk_appetite"]),
    ],
)
def test_incomplete_directional_evidence_stays_undecided(
    tones: tuple[str | None, str | None, str | None],
    valid_count: int,
    missing_keys: list[str],
) -> None:
    cards = [
        {"key": key, "tone": tone}
        for key, tone in zip(("liquidity", "risk_appetite", "credit"), tones)
    ]
    cards.append({"key": "outputs", "tone": "positive"})

    conclusion = _analysis_conclusion(cards, {"hit_rate": 1.0})

    assert conclusion["tone"] == "missing"
    assert conclusion["stance"] == "暂不判断"
    assert f"{valid_count}/3" in conclusion["summary"]
    basis = conclusion["basis"]
    assert basis["directional_coverage"] == {
        "expected_count": 3,
        "valid_count": valid_count,
        "missing_keys": missing_keys,
        "status": "insufficient",
    }
    assert len(basis["signal_cards"]) == valid_count
    assert all(card["key"] != "outputs" for card in basis["signal_cards"])


def test_absent_directional_cards_are_reported_as_missing() -> None:
    conclusion = _analysis_conclusion(
        [{"key": "outputs", "tone": "positive"}], {"hit_rate": 1.0}
    )

    assert conclusion["tone"] == "missing"
    assert conclusion["basis"]["signal_cards"] == []
    assert conclusion["basis"]["directional_coverage"]["missing_keys"] == [
        "credit", "liquidity", "risk_appetite"
    ]


@pytest.mark.parametrize(
    ("tones", "expected_tone"),
    [
        (("positive", "positive", "neutral"), "positive"),
        (("negative", "neutral", "negative"), "negative"),
        (("positive", "negative", "neutral"), "neutral"),
        (("neutral", "neutral", "neutral"), "neutral"),
    ],
)
def test_complete_directional_evidence_preserves_existing_vote(
    tones: tuple[str, str, str], expected_tone: str
) -> None:
    cards = [
        {"key": key, "tone": tone}
        for key, tone in zip(("liquidity", "risk_appetite", "credit"), tones)
    ]

    conclusion = _analysis_conclusion(cards, {"hit_rate": 1.0})

    assert conclusion["tone"] == expected_tone
    assert conclusion["basis"]["directional_coverage"] == {
        "expected_count": 3,
        "valid_count": 3,
        "missing_keys": [],
        "status": "complete",
    }


def test_low_indicator_hit_rate_retains_existing_gate_with_directional_basis() -> None:
    cards = [
        {"key": key, "tone": "positive"}
        for key in ("liquidity", "risk_appetite", "credit")
    ]

    conclusion = _analysis_conclusion(cards, {"hit_rate": 0.59})

    assert conclusion["stance"] == "数据不足"
    assert conclusion["tone"] == "missing"
    assert "核心指标命中不足" in conclusion["summary"]
    assert conclusion["basis"]["directional_coverage"]["valid_count"] == 3
