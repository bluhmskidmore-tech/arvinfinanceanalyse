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
    sector_code: str = "801080",
    sector_name: str = "Electronic",
    close_value: float | None = 10.0,
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
    concept_source_kind: str = "real_concept",
) -> ThemeBreakoutSnapshot:
    return ThemeBreakoutSnapshot(
        stock_code=stock_code,
        stock_name=stock_name,
        sector_code=sector_code,
        sector_name=sector_name,
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
        concept_source_kind=concept_source_kind,
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
    assert semiconductor["theme_name"] == "半导体"
    assert semiconductor["proxy_code"] == "S270000"
    assert semiconductor["parent_sector_rank"] == 9
    assert semiconductor["member_count"] == 3
    assert semiconductor["strong_stock_count"] == 3
    assert semiconductor["limit_stock_count"] == 2
    assert semiconductor["avg_pctchange"] == 9.766667
    assert semiconductor["observation_only"] is True
    assert "proxy" in str(semiconductor["reason"]).lower()

    stock_items = cast(list[dict[str, Any]], semiconductor["items"])
    assert [item["stock_code"] for item in stock_items] == [
        "688001.SH",
        "688002.SH",
        "688003.SH",
    ]
    assert stock_items[0]["closed_up_limit"] is True
    assert {item["concept_source_kind"] for item in stock_items} == {"proxy"}

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
    assert concept["proxy_code"] == ""
    assert concept["movement_event_count"] == 2
    assert concept["latest_event_title"] == "Chiplet concept extends gains"
    assert concept["latest_event_time"] == "2026-05-08 10:08:00"
    assert concept["observation_only"] is True
    assert "proxy" not in str(concept["reason"]).lower()


def test_current_overlay_source_is_visible_on_theme_and_nested_stock_rows() -> None:
    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[
            _snapshot(
                stock_code=f"68800{index}.SH",
                stock_name=f"Overlay member {index}",
                pctchange=8.0 - index,
                closed_up_limit=index < 2,
                concept_code="885002.TI",
                concept_name="Financial technology",
                concept_source_kind="tushare_current_overlay",
            )
            for index in range(1, 4)
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["formula_version"] == "rv_livermore_theme_breakout_multi_proxy_v6"
    assert payload["is_proxy"] is False
    theme = cast(list[dict[str, Any]], payload["items"])[0]
    assert theme["source_kind"] == "tushare_current_overlay"
    assert "current overlay" in str(theme["reason"]).lower()
    assert {
        stock["concept_source_kind"]
        for stock in cast(list[dict[str, Any]], theme["items"])
    } == {"tushare_current_overlay"}


def test_theme_breakout_review_items_are_additive_capped_and_carry_failed_gate_codes() -> (
    None
):
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
        snapshots=[
            *selected_group,
            *cluster_strength_review,
            *breadth_review,
            *filler_groups,
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    selected_items = cast(list[dict[str, Any]], payload["items"])
    review_items = cast(list[dict[str, Any]], payload["review_items"])
    review_by_key = {str(item["theme_key"]): item for item in review_items}

    assert [item["theme_key"] for item in selected_items] == ["concept:C100"]
    assert len(review_items) == MAX_REVIEW_ITEMS
    assert review_by_key["concept:C200"]["failed_gate_codes"] == [
        "insufficient_cluster_strength"
    ]
    assert review_by_key["concept:C200"]["failed_gates"] == [
        "insufficient_cluster_strength"
    ]
    assert review_by_key["concept:C210"]["failed_gate_codes"] == [
        "insufficient_breadth"
    ]
    assert review_by_key["concept:C210"]["failed_gates"] == ["insufficient_breadth"]
    assert f"concept:CF{MAX_REVIEW_ITEMS + 1:02d}" not in review_by_key

    serialized = str(review_items).lower()
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "order" not in serialized


def test_theme_breakout_breadth_gate_uses_full_concept_membership() -> None:
    strong_members = [
        _snapshot(
            stock_code=f"6881{index:02d}.SH",
            stock_name=f"Narrow Rally Leader {index}",
            pctchange=7.2,
            concept_code="C300",
            concept_name="Narrow Rally",
        )
        for index in range(3)
    ]
    lagging_members = [
        _snapshot(
            stock_code=f"6882{index:02d}.SH",
            stock_name=f"Narrow Rally Laggard {index}",
            pctchange=-0.5,
            concept_code="C300",
            concept_name="Narrow Rally",
        )
        for index in range(97)
    ]

    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[*strong_members, *lagging_members],
    )

    payload = cast(dict[str, Any], result.payload)
    selected_keys = [item["theme_key"] for item in cast(list[dict[str, Any]], payload["items"])]
    assert "concept:C300" not in selected_keys

    review_by_key = {
        str(item["theme_key"]): item
        for item in cast(list[dict[str, Any]], payload["review_items"])
    }
    theme = review_by_key["concept:C300"]
    assert theme["failed_gate_codes"] == ["insufficient_breadth"]
    assert theme["member_count"] == 100
    assert theme["advance_count"] == 3
    assert theme["advance_ratio"] == 0.03
    assert theme["strong_stock_count"] == 3
    assert theme["limit_stock_count"] == 0
    assert theme["avg_pctchange"] == round((3 * 7.2 + 97 * -0.5) / 100, 6)
    stock_items = cast(list[dict[str, Any]], theme["items"])
    assert {item["stock_code"] for item in stock_items} == {
        "688100.SH",
        "688101.SH",
        "688102.SH",
    }


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


def test_theme_breakout_keeps_strong_stock_when_sector_rank_missing() -> None:
    result = compute_theme_breakout(
        as_of_date="2026-05-08",
        snapshots=[
            _snapshot(
                stock_code="688001.SH",
                stock_name="Alpha Semiconductor",
                pctchange=12.1,
                closed_up_limit=True,
                sector_rank=5,
            ),
            _snapshot(
                stock_code="688002.SH",
                stock_name="Beta Chip",
                pctchange=10.4,
                closed_up_limit=True,
                turn=5.2,
                sector_rank=None,
            ),
            _snapshot(
                stock_code="688003.SH",
                stock_name="Gamma Micro",
                pctchange=6.8,
                sector_rank=None,
            ),
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert payload["theme_count"] == 1
    stock_items = cast(list[dict[str, Any]], items[0]["items"])
    stock_codes = [item["stock_code"] for item in stock_items]
    assert "688002.SH" in stock_codes
    assert "688003.SH" in stock_codes
    missing_rank_rows = [row for row in stock_items if row.get("sector_rank_missing")]
    assert len(missing_rank_rows) == 2
    assert all(row["sector_rank"] is None for row in missing_rank_rows)
    ranked_row = next(row for row in stock_items if row["stock_code"] == "688001.SH")
    assert ranked_row["sector_rank"] == 5
    assert stock_codes.index("688001.SH") < stock_codes.index("688002.SH")
    assert stock_codes.index("688001.SH") < stock_codes.index("688003.SH")


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


def _semiconductor_cluster() -> list[ThemeBreakoutSnapshot]:
    return [
        _snapshot(
            stock_code="688001.SH",
            stock_name="国科半导体",
            pctchange=12.1,
            closed_up_limit=True,
        ),
        _snapshot(
            stock_code="688002.SH",
            stock_name="华芯微",
            pctchange=10.4,
            closed_up_limit=True,
            turn=5.2,
        ),
        _snapshot(
            stock_code="688003.SH",
            stock_name="晶圆先锋",
            pctchange=6.8,
            turn=3.8,
        ),
    ]


def _broker_cluster(*, pctchange: float = 9.0, closed_up_limit: bool = True) -> list[ThemeBreakoutSnapshot]:
    return [
        _snapshot(
            stock_code=f"60083{index}.SH",
            stock_name=f"东部证券{index}",
            pctchange=pctchange,
            closed_up_limit=closed_up_limit,
            sector_code="S490000",
            sector_name="非银金融",
            sector_rank=4,
        )
        for index in range(3)
    ]


def test_multi_proxy_pool_groups_output_by_theme_with_proxy_codes() -> None:
    result = compute_theme_breakout(
        as_of_date="2026-08-11",
        snapshots=[*_semiconductor_cluster(), *_broker_cluster()],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["is_proxy"] is True
    assert payload["theme_count"] == 2

    items = cast(list[dict[str, Any]], payload["items"])
    by_key = {str(item["theme_key"]): item for item in items}
    assert set(by_key) == {"semiconductor_proxy", "broker_proxy"}

    semiconductor = by_key["semiconductor_proxy"]
    assert semiconductor["theme_name"] == "半导体"
    assert semiconductor["proxy_code"] == "S270000"
    assert semiconductor["source_kind"] == "proxy"
    assert {str(row["stock_code"]) for row in cast(list[dict[str, Any]], semiconductor["items"])} == {
        "688001.SH",
        "688002.SH",
        "688003.SH",
    }

    broker = by_key["broker_proxy"]
    assert broker["theme_name"] == "券商"
    assert broker["proxy_code"] == "S490000"
    assert broker["source_kind"] == "proxy"
    assert {str(row["stock_code"]) for row in cast(list[dict[str, Any]], broker["items"])} == {
        "600830.SH",
        "600831.SH",
        "600832.SH",
    }

    # 每个题材独立评估：排名字段存在且互不共享成员。
    assert {item["rank"] for item in items} == {1, 2}


def test_multi_proxy_only_breaking_theme_is_selected() -> None:
    quiet_defense = [
        _snapshot(
            stock_code=f"60076{index}.SH",
            stock_name=f"航空工业{index}",
            pctchange=0.4,
            sector_code="S650000",
            sector_name="国防军工",
        )
        for index in range(4)
    ]

    result = compute_theme_breakout(
        as_of_date="2026-08-11",
        snapshots=[*_semiconductor_cluster(), *quiet_defense],
    )

    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert [item["theme_key"] for item in items] == ["semiconductor_proxy"]
    # 无突破行的题材既不进 items 也不进 review_items（fail-closed，不造近似信号）。
    review_keys = {str(item["theme_key"]) for item in cast(list[dict[str, Any]], payload["review_items"])}
    assert "defense_proxy" not in review_keys


def test_multi_proxy_near_miss_theme_lands_in_review_with_proxy_code() -> None:
    narrow_pharma = [
        _snapshot(
            stock_code="600550.SH",
            stock_name="康泰生物医药",
            pctchange=10.0,
            closed_up_limit=True,
            sector_code="S370000",
            sector_name="医药生物",
        ),
        *[
            _snapshot(
                stock_code=f"60055{index}.SH",
                stock_name=f"平稳医药{index}",
                pctchange=-0.2,
                sector_code="S370000",
                sector_name="医药生物",
            )
            for index in range(1, 6)
        ],
    ]

    result = compute_theme_breakout(
        as_of_date="2026-08-11",
        snapshots=[*_semiconductor_cluster(), *narrow_pharma],
    )

    payload = cast(dict[str, Any], result.payload)
    selected_keys = [str(item["theme_key"]) for item in cast(list[dict[str, Any]], payload["items"])]
    assert selected_keys == ["semiconductor_proxy"]

    review_by_key = {
        str(item["theme_key"]): item for item in cast(list[dict[str, Any]], payload["review_items"])
    }
    pharma = review_by_key["pharma_proxy"]
    assert pharma["theme_name"] == "医药"
    assert pharma["proxy_code"] == "S370000"
    assert pharma["member_count"] == 6
    assert set(cast(list[str], pharma["failed_gate_codes"])) == {
        "insufficient_cluster_strength",
        "insufficient_breadth",
    }


def test_multi_proxy_missing_market_data_fails_closed_per_theme() -> None:
    broken_broker = [
        _snapshot(
            stock_code=f"60083{index}.SH",
            stock_name=f"东部证券{index}",
            pctchange=9.0,
            closed_up_limit=True,
            sector_code="S490000",
            sector_name="非银金融",
            close_value=None,
        )
        for index in range(3)
    ]

    result = compute_theme_breakout(
        as_of_date="2026-08-11",
        snapshots=[*_semiconductor_cluster(), *broken_broker],
    )

    payload = cast(dict[str, Any], result.payload)
    selected_keys = [str(item["theme_key"]) for item in cast(list[dict[str, Any]], payload["items"])]
    assert selected_keys == ["semiconductor_proxy"]
    review_keys = {str(item["theme_key"]) for item in cast(list[dict[str, Any]], payload["review_items"])}
    assert "broker_proxy" not in review_keys


def test_whole_sector_proxy_matches_members_without_name_keywords() -> None:
    defense_breakout = [
        _snapshot(
            stock_code=f"60076{index}.SH",
            stock_name=f"任意名称{index}",
            pctchange=8.5,
            closed_up_limit=index == 0,
            sector_code="S650000",
            sector_name="国防军工",
        )
        for index in range(3)
    ]
    lagging_member = _snapshot(
        stock_code="600769.SH",
        stock_name="滞涨军工",
        pctchange=-1.0,
        sector_code="S650000",
        sector_name="国防军工",
    )

    result = compute_theme_breakout(
        as_of_date="2026-08-11",
        snapshots=[*defense_breakout, lagging_member],
    )

    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert [item["theme_key"] for item in items] == ["defense_proxy"]
    defense = items[0]
    assert defense["theme_name"] == "国防军工"
    assert defense["proxy_code"] == "S650000"
    # 无关键词=整行业篮子：广度统计覆盖全部行业成员（含滞涨股）。
    assert defense["member_count"] == 4
    assert defense["advance_count"] == 3
