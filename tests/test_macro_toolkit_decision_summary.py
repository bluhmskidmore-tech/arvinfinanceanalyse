"""Decision summary (M16) aggregation card contract.

The backend aggregates M7-M15 + Crisis capability cards into one
decision-summary card. The card denominator must match the real number of
aggregated capability cards instead of a hardcoded "/9", and the capability
definition metadata must not claim the aggregation is still unwired.
"""

from __future__ import annotations

from datetime import date

import backend.app.api.routes.macro_toolkit as macro_toolkit_route


def _make_card(key: str, status: str, tone: str) -> dict[str, object]:
    return {
        "key": key,
        "legacy_module": key.upper(),
        "label": key,
        "group": "test",
        "status": status,
        "tone": tone,
        "headline": f"{key} headline",
    }


def _decision_definition() -> dict[str, object]:
    return next(
        item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == "decision_summary"
    )


def test_decision_summary_denominator_matches_aggregated_card_count() -> None:
    non_decision_count = len(macro_toolkit_route._CAPABILITY_DEFINITIONS) - 1
    cards = [_make_card(f"m{index}", "complete", "positive") for index in range(non_decision_count)]

    card = macro_toolkit_route._decision_summary_card(_decision_definition(), cards, date(2026, 7, 10))

    assert card["primary_metric"]["unit"] == f"/{non_decision_count}"
    assert card["primary_metric"]["value"] == non_decision_count
    assert card["status"] == "complete"


def test_decision_summary_excludes_observation_cards_from_tone_voting() -> None:
    observation_keys = ["merrill_clock_cn", "cta_trend_cn", "dcc_garch_cn", "risk_parity_cn"]
    cards = [
        _make_card("m7", "complete", "neutral"),
        _make_card("m8", "complete", "neutral"),
        *[_make_card(key, "complete", "positive") for key in observation_keys],
    ]

    card = macro_toolkit_route._decision_summary_card(_decision_definition(), cards, date(2026, 7, 10))

    # 4 张 observation 卡全是 positive，也不得驱动方向性久期/信用建议
    assert card["tone"] == "neutral"
    assert card["result"]["positive_count"] == 0
    assert card["result"]["negative_count"] == 0
    assert card["result"]["observation_excluded_count"] == 4
    assert card["score"] == 50.0
    # observation 卡仍计入可用分母
    assert card["result"]["usable_count"] == 6
    assert card["primary_metric"]["value"] == 6
    assert card["primary_metric"]["unit"] == "/6"
    assert card["result"]["formal_use_allowed"] is False


def test_decision_summary_result_marks_formal_use_not_allowed() -> None:
    cards = [_make_card("m7", "complete", "positive")]

    card = macro_toolkit_route._decision_summary_card(_decision_definition(), cards, date(2026, 7, 10))

    assert card["result"]["formal_use_allowed"] is False
    assert card["tone"] == "positive"
    assert card["result"]["positive_count"] == 1


def test_decision_summary_marks_degraded_when_any_module_unavailable() -> None:
    cards = [
        _make_card("m7", "complete", "positive"),
        _make_card("m8", "degraded", "negative"),
        _make_card("m9", "unavailable", "missing"),
    ]

    card = macro_toolkit_route._decision_summary_card(_decision_definition(), cards, date(2026, 7, 10))

    assert card["status"] == "degraded"
    assert card["primary_metric"]["unit"] == "/3"
    assert card["primary_metric"]["value"] == 2
    assert card["result"]["missing_count"] == 1


def test_decision_summary_with_all_modules_unavailable_does_not_claim_neutral_stance() -> None:
    cards = [_make_card(f"m{index}", "unavailable", "missing") for index in range(10)]

    card = macro_toolkit_route._decision_summary_card(_decision_definition(), cards, date(2026, 7, 10))

    assert card["status"] == "unavailable"
    assert card["tone"] == "missing"
    assert "中性观察" not in str(card["headline"])
    assert "分化" not in str(card["headline"])
    assert card["result"]["usable_count"] == 0


def test_decision_summary_counts_all_non_decision_definitions_regardless_of_order() -> None:
    original = macro_toolkit_route._CAPABILITY_DEFINITIONS
    decision = next(item for item in original if item["key"] == "decision_summary")
    others = [item for item in original if item["key"] != "decision_summary"]
    reordered = tuple([others[0], decision, *others[1:]])
    try:
        macro_toolkit_route._CAPABILITY_DEFINITIONS = reordered
        cards = macro_toolkit_route._assemble_capability_cards(
            {},
            date(2026, 7, 10),
        )
    finally:
        macro_toolkit_route._CAPABILITY_DEFINITIONS = original

    decision_card = next(item for item in cards if item["key"] == "decision_summary")
    assert decision_card["primary_metric"]["unit"] == f"/{len(others)}"
    assert len(cards) == len(original)


def test_decision_summary_definition_metadata_reflects_wired_aggregation() -> None:
    definition = _decision_definition()

    assert definition["implementation_status"] != "not_wired"
    assert definition["route_status"] == "wired"
    assert definition["frontend_status"] == "visible"
    assert "而不是前端拼文案" not in str(definition["next_step"])
