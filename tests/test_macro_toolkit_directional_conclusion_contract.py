"""Macro-toolkit directional conclusions use business signals only."""

from __future__ import annotations

import pytest

from backend.app.services.macro_toolkit_analysis_service import _script_output_card
from backend.app.services.macro_toolkit_route_support import _analysis_conclusion

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _card(key: str, tone: str) -> dict[str, object]:
    return {"key": key, "tone": tone}


def test_many_script_outputs_remain_visible_but_cannot_make_conclusion_positive() -> None:
    output_card = _script_output_card(
        [
            {
                "name": f"output-{index}.csv",
                "modified_at": f"2026-08-25T12:{index:02d}:00+08:00",
            }
            for index in range(20)
        ]
    )
    cards = [
        _card("liquidity", "neutral"),
        _card("risk_appetite", "neutral"),
        _card("credit", "neutral"),
        output_card,
    ]

    conclusion = _analysis_conclusion(cards, {"hit_rate": 1.0})

    assert output_card["key"] == "outputs"
    assert output_card["tone"] == "positive"
    assert output_card["score"] == 100
    assert "20 个输出文件" in output_card["evidence"]
    assert conclusion["tone"] == "neutral"
    assert conclusion["stance"] == "中性观察"


@pytest.mark.parametrize(
    ("directional_tones", "operational_tone", "expected_tone"),
    [
        (("positive", "positive", "neutral"), "negative", "positive"),
        (("negative", "neutral", "negative"), "positive", "negative"),
        (("positive", "negative", "neutral"), "positive", "neutral"),
    ],
)
def test_only_allowlisted_business_signals_vote_on_direction(
    directional_tones: tuple[str, str, str],
    operational_tone: str,
    expected_tone: str,
) -> None:
    cards = [
        _card("liquidity", directional_tones[0]),
        _card("risk_appetite", directional_tones[1]),
        _card("credit", directional_tones[2]),
        _card("outputs", operational_tone),
        _card("future_operational_card", operational_tone),
    ]

    conclusion = _analysis_conclusion(cards, {"hit_rate": 1.0})

    assert conclusion["tone"] == expected_tone
