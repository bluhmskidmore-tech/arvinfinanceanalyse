from __future__ import annotations

from typing import Any, cast

from backend.app.core_finance.livermore_theme_breakout import (
    FORMULA_VERSION,
    MAX_REVIEW_ITEMS,
    MAX_THEMES,
    ThemeBreakoutSnapshot,
    compute_theme_breakout,
)


def _snapshot(
    *,
    stock_code: str,
    stock_name: str,
    pctchange: float,
    closed_up_limit: bool = False,
    sector_rank: int = 9,
    close_value: float = 10.0,
    high_value: float = 10.1,
    low_value: float = 9.4,
    open_value: float = 9.6,
    turn: float = 4.2,
    amplitude: float = 7.0,
    concept_code: str = "",
    concept_name: str = "",
    movement_event_count: int = 0,
    latest_event_title: str = "",
    latest_event_time: str = "",
) -> ThemeBreakoutSnapshot:
    return ThemeBreakoutSnapshot(
        stock_code=stock_code,
        stock_name=stock_name,
        sector_code="801080",
        sector_name="Electronic",
        sector_rank=sector_rank,
        open_value=open_value,
        high_value=high_value,
        low_value=low_value,
        close_value=close_value,
        pctchange=pctchange,
        turn=turn,
        amplitude=amplitude,
        closed_up_limit=closed_up_limit,
        concept_code=concept_code,
        concept_name=concept_name,
        movement_event_count=movement_event_count,
        latest_event_title=latest_event_title,
        latest_event_time=latest_event_time,
    )


def test_theme_breakout_surfaces_semiconductor_proxy_outside_top_three_sector() -> None:
    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[
            _snapshot(
                stock_code="688001.SH",
                stock_name="Alpha Semiconductor",
                pctchange=12.1,
                closed_up_limit=True,
            ),
            _snapshot(
                stock_code="688002.SH",
                stock_name="Beta Chip",
                pctchange=10.4,
                closed_up_limit=True,
                turn=5.2,
            ),
            _snapshot(
                stock_code="688003.SH",
                stock_name="Gamma Micro",
                pctchange=6.8,
                turn=3.8,
            ),
            _snapshot(
                stock_code="000001.SZ",
                stock_name="Bank Alpha",
                pctchange=0.8,
                sector_rank=1,
                turn=1.1,
                amplitude=1.2,
            ),
        ],
    )

    payload = cast(dict[str, Any], result.payload)

    assert payload["as_of_date"] == "2026-05-08"
    assert payload["formula_version"] == FORMULA_VERSION
    assert payload["is_proxy"] is True
    assert payload["theme_count"] == 1

    items = cast(list[dict[str, Any]], payload["items"])
    assert [item["theme_key"] for item in items] == ["semiconductor_proxy"]
    semiconductor = items[0]
    assert semiconductor["parent_sector_rank"] == 9
    assert semiconductor["member_count"] == 3
    assert semiconductor["strong_stock_count"] == 3
    assert semiconductor["limit_stock_count"] == 2
    assert semiconductor["avg_pctchange"] == 9.766667
    assert semiconductor["observation_only"] is True
    assert "proxy" in str(semiconductor["reason"]).lower()

    stock_items = cast(list[dict[str, Any]], semiconductor["items"])
    assert [item["stock_code"] for item in stock_items] == ["688001.SH", "688002.SH", "688003.SH"]
    assert stock_items[0]["closed_up_limit"] is True

    serialized = str(payload).lower()
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "order" not in serialized


def test_theme_breakout_prefers_real_concept_and_movement_rows_over_proxy() -> None:
    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[
            _snapshot(
                stock_code="688001.SH",
                stock_name="Alpha Semiconductor",
                pctchange=12.1,
                closed_up_limit=True,
                concept_code="C001",
                concept_name="Chiplet",
                movement_event_count=1,
                latest_event_title="Chiplet concept intraday surge",
                latest_event_time="2026-05-08 10:05:00",
            ),
            _snapshot(
                stock_code="688002.SH",
                stock_name="Beta Chip",
                pctchange=10.4,
                closed_up_limit=True,
                concept_code="C001",
                concept_name="Chiplet",
                movement_event_count=1,
                latest_event_title="Chiplet concept extends gains",
                latest_event_time="2026-05-08 10:08:00",
            ),
            _snapshot(
                stock_code="688003.SH",
                stock_name="Gamma Micro",
                pctchange=6.8,
                concept_code="C001",
                concept_name="Chiplet",
            ),
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["is_proxy"] is False
    items = cast(list[dict[str, Any]], payload["items"])
    assert [item["theme_key"] for item in items] == ["concept:C001"]
    concept = items[0]
    assert concept["theme_name"] == "Chiplet"
    assert concept["source_kind"] == "real_concept"
    assert concept["movement_event_count"] == 2
    assert concept["latest_event_title"] == "Chiplet concept extends gains"
    assert concept["latest_event_time"] == "2026-05-08 10:08:00"
    assert concept["observation_only"] is True
    assert "proxy" not in str(concept["reason"]).lower()


def test_theme_breakout_review_items_are_additive_capped_and_carry_failed_gate_codes() -> None:
    selected_group = [
        _snapshot(
            stock_code="688100.SH",
            stock_name="Leader Selected Alpha",
            pctchange=12.1,
            closed_up_limit=True,
            concept_code="C100",
            concept_name="Selected Cluster",
        ),
        _snapshot(
            stock_code="688101.SH",
            stock_name="Leader Selected Beta",
            pctchange=9.8,
            closed_up_limit=True,
            turn=5.0,
            concept_code="C100",
            concept_name="Selected Cluster",
        ),
        _snapshot(
            stock_code="688102.SH",
            stock_name="Leader Selected Gamma",
            pctchange=6.4,
            concept_code="C100",
            concept_name="Selected Cluster",
        ),
    ]
    cluster_strength_review = [
        _snapshot(
            stock_code="688200.SH",
            stock_name="Review Strength Alpha",
            pctchange=6.8,
            concept_code="C200",
            concept_name="Cluster Strength Review",
        ),
        _snapshot(
            stock_code="688201.SH",
            stock_name="Review Strength Beta",
            pctchange=5.6,
            concept_code="C200",
            concept_name="Cluster Strength Review",
        ),
        _snapshot(
            stock_code="688202.SH",
            stock_name="Review Strength Gamma",
            pctchange=0.0,
            closed_up_limit=True,
            concept_code="C200",
            concept_name="Cluster Strength Review",
        ),
    ]
    breadth_review = [
        _snapshot(
            stock_code="688210.SH",
            stock_name="Review Breadth Alpha",
            pctchange=0.0,
            closed_up_limit=True,
            concept_code="C210",
            concept_name="Breadth Review",
        ),
        _snapshot(
            stock_code="688211.SH",
            stock_name="Review Breadth Beta",
            pctchange=0.0,
            closed_up_limit=True,
            concept_code="C210",
            concept_name="Breadth Review",
        ),
        _snapshot(
            stock_code="688212.SH",
            stock_name="Review Breadth Gamma",
            pctchange=0.0,
            concept_code="C210",
            concept_name="Breadth Review",
            closed_up_limit=True,
        ),
    ]
    filler_groups = []
    for index in range(MAX_REVIEW_ITEMS + 2):
        filler_groups.extend(
            [
                _snapshot(
                    stock_code=f"689{index:02d}1.SH",
                    stock_name=f"Filler Review Alpha {index}",
                    pctchange=5.2,
                    concept_code=f"CF{index:02d}",
                    concept_name=f"Filler Review {index}",
                ),
                _snapshot(
                    stock_code=f"689{index:02d}2.SH",
                    stock_name=f"Filler Review Beta {index}",
                    pctchange=0.0,
                    closed_up_limit=True,
                    concept_code=f"CF{index:02d}",
                    concept_name=f"Filler Review {index}",
                ),
            ]
        )

    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[*selected_group, *cluster_strength_review, *breadth_review, *filler_groups],
    )

    payload = cast(dict[str, Any], result.payload)
    selected_items = cast(list[dict[str, Any]], payload["items"])
    review_items = cast(list[dict[str, Any]], payload["review_items"])
    review_by_key = {str(item["theme_key"]): item for item in review_items}

    assert [item["theme_key"] for item in selected_items] == ["concept:C100"]
    assert len(review_items) == MAX_REVIEW_ITEMS
    assert review_by_key["concept:C200"]["failed_gate_codes"] == ["insufficient_cluster_strength"]
    assert review_by_key["concept:C200"]["failed_gates"] == ["insufficient_cluster_strength"]
    assert review_by_key["concept:C210"]["failed_gate_codes"] == ["insufficient_breadth"]
    assert review_by_key["concept:C210"]["failed_gates"] == ["insufficient_breadth"]
    assert f"concept:CF{MAX_REVIEW_ITEMS + 1:02d}" not in review_by_key

    serialized = str(review_items).lower()
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "order" not in serialized


def test_theme_breakout_caps_selected_real_concepts_to_ranked_top_themes() -> None:
    snapshots: list[ThemeBreakoutSnapshot] = []
    for theme_index in range(MAX_THEMES + 5):
        for stock_index in range(3):
            snapshots.append(
                _snapshot(
                    stock_code=f"688{theme_index:03d}{stock_index}.SH",
                    stock_name=f"Theme {theme_index} Stock {stock_index}",
                    pctchange=12.0 - theme_index * 0.01,
                    concept_code=f"C{theme_index:03d}",
                    concept_name=f"Theme {theme_index}",
                )
            )

    result = compute_theme_breakout(as_of_date="2026-05-08", snapshots=snapshots)

    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert payload["theme_count"] == MAX_THEMES
    assert len(items) == MAX_THEMES
    assert items[0]["theme_key"] == "concept:C000"
    assert items[-1]["theme_key"] == f"concept:C{MAX_THEMES - 1:03d}"


def test_theme_breakout_ranking_uses_movement_events_as_confirmation_signal() -> None:
    movement_confirmed = [
        _snapshot(
            stock_code=f"68810{index}.SH",
            stock_name=f"Movement Confirmed {index}",
            pctchange=8.0,
            closed_up_limit=index == 0,
            concept_code="CMOVE",
            concept_name="Movement Confirmed",
            movement_event_count=1,
            latest_event_title="Movement event",
            latest_event_time="2026-05-08 10:00:00",
        )
        for index in range(3)
    ]
    higher_average_without_events = [
        _snapshot(
            stock_code=f"68820{index}.SH",
            stock_name=f"No Event {index}",
            pctchange=9.0,
            closed_up_limit=index == 0,
            concept_code="CNOEVENT",
            concept_name="No Event",
        )
        for index in range(3)
    ]

    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[*higher_average_without_events, *movement_confirmed],
    )

    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert items[0]["theme_key"] == "concept:CMOVE"
    assert items[0]["movement_event_count"] == 3
