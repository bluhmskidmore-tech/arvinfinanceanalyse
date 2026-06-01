from __future__ import annotations

from typing import Any, cast

import pytest

from backend.app.core_finance.livermore_sector_rank import (
    PROVISIONAL_FORMULA_VERSION,
    SectorRankConstituent,
    compute_sector_rank,
)


def test_sector_rank_uses_provisional_percentile_formula_and_tie_breaks() -> None:
    result = compute_sector_rank(
        as_of_date="2026-04-06",
        rows=[
            SectorRankConstituent("000001.SZ", "801780", "Bank", 4.0, 4.0, 4.0),
            SectorRankConstituent("600000.SH", "801780", "Bank", 6.0, 6.0, 6.0),
            SectorRankConstituent("000002.SZ", "801010", "Agriculture", 4.0, 3.0, 1.0),
            SectorRankConstituent("000003.SZ", "801020", "Mining", 3.0, 4.0, 3.0),
            SectorRankConstituent("000004.SZ", "801030", "Manufacturing", 3.0, 4.0, 3.0),
        ],
    )

    assert result.ready is True
    assert result.payload is not None
    payload = cast(dict[str, Any], result.payload)
    assert payload["as_of_date"] == "2026-04-06"
    assert payload["formula_version"] == PROVISIONAL_FORMULA_VERSION
    assert payload["is_provisional"] is True
    assert payload["sector_count"] == 4
    assert payload["excluded_constituent_count"] == 0
    assert payload["excluded_sector_count"] == 0
    items = cast(list[dict[str, Any]], payload["items"])
    assert [row["sector_code"] for row in items] == ["801780", "801020", "801030", "801010"]
    assert [row["rank"] for row in items] == [1, 2, 3, 4]
    assert items[0]["score"] == pytest.approx(1.0)
    assert items[0]["avg_pctchange"] == pytest.approx(5.0)
    assert items[0]["avg_turn"] == pytest.approx(5.0)
    assert items[0]["avg_amplitude"] == pytest.approx(5.0)
    assert items[0]["constituent_count"] == 2


def test_sector_rank_attaches_leader_constituents_by_turn() -> None:
    result = compute_sector_rank(
        as_of_date="2026-04-06",
        rows=[
            SectorRankConstituent("000001.SZ", "801780", "Bank", 4.0, 4.0, 4.0, "Bank A"),
            SectorRankConstituent("600000.SH", "801780", "Bank", 6.0, 6.0, 6.0, "Bank B"),
            SectorRankConstituent("000002.SZ", "801010", "Agriculture", 4.0, 3.0, 1.0, "Agri A"),
            SectorRankConstituent("000003.SZ", "801020", "Mining", 3.0, 4.0, 3.0, "Mine A"),
            SectorRankConstituent("000004.SZ", "801030", "Manufacturing", 3.0, 4.0, 3.0, "Mfg A"),
        ],
        leader_constituents_per_sector=2,
    )

    assert result.ready is True
    assert result.payload is not None
    payload = cast(dict[str, Any], result.payload)
    assert payload["leader_constituent_limit"] == 2
    assert payload["leader_constituent_method"] == "top_turn_same_day"
    items = cast(list[dict[str, Any]], payload["items"])
    bank = next(row for row in items if row["sector_code"] == "801780")
    leaders = cast(list[dict[str, Any]], bank["leader_constituents"])
    assert [leader["stock_code"] for leader in leaders] == ["600000.SH", "000001.SZ"]
    assert leaders[0]["stock_name"] == "Bank B"
    assert leaders[0]["turn"] == pytest.approx(6.0)


def test_sector_rank_excludes_invalid_constituents_and_empty_sectors() -> None:
    result = compute_sector_rank(
        as_of_date="2026-04-06",
        rows=[
            SectorRankConstituent("000001.SZ", "801780", "Bank", 3.0, 2.0, 1.0),
            SectorRankConstituent("000002.SZ", "801010", "Agriculture", 5.0, 1.0, 2.0),
            SectorRankConstituent("000003.SZ", "801020", "Mining", 4.0, 3.0, 2.0),
            SectorRankConstituent("000004.SZ", "801999", "InvalidOnly", None, 3.0, 2.0),
            SectorRankConstituent("000005.SZ", "", "", 9.0, 9.0, 9.0),
            SectorRankConstituent("000006.SZ", "801780", "Bank", float("nan"), 9.0, 9.0),
            SectorRankConstituent("000007.SZ", "801998", "InfiniteOnly", 1.0, float("inf"), 2.0),
        ],
    )

    assert result.ready is True
    assert result.payload is not None
    payload = cast(dict[str, Any], result.payload)
    assert payload["sector_count"] == 3
    assert payload["excluded_constituent_count"] == 4
    assert payload["excluded_sector_count"] == 2
    items = cast(list[dict[str, Any]], payload["items"])
    assert [row["sector_code"] for row in items] == ["801020", "801010", "801780"]


def test_sector_rank_scores_code_name_aggregate_keys_independently() -> None:
    result = compute_sector_rank(
        as_of_date="2026-04-06",
        rows=[
            SectorRankConstituent("000001.SZ", "801001", "Alpha", 10.0, 1.0, 1.0),
            SectorRankConstituent("000002.SZ", "801001", "AlphaAlias", 1.0, 1.0, 1.0),
            SectorRankConstituent("000003.SZ", "801002", "Beta", 5.0, 1.0, 1.0),
            SectorRankConstituent("000004.SZ", "801003", "Gamma", 3.0, 1.0, 1.0),
        ],
    )

    assert result.ready is True
    assert result.payload is not None
    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert items[0]["sector_code"] == "801001"
    assert items[0]["sector_name"] == "Alpha"
    assert items[0]["score"] > items[1]["score"]


def test_sector_rank_requires_three_rankable_sectors() -> None:
    result = compute_sector_rank(
        as_of_date="2026-04-06",
        rows=[
            SectorRankConstituent("000001.SZ", "801780", "Bank", 3.0, 2.0, 1.0),
            SectorRankConstituent("000002.SZ", "801010", "Agriculture", 5.0, 1.0, 2.0),
            SectorRankConstituent("000003.SZ", "801999", "InvalidOnly", None, 1.0, 1.0),
        ],
    )

    assert result.ready is False
    assert result.payload is None
    assert result.rankable_sector_count == 2
    assert result.excluded_constituent_count == 1
    assert result.excluded_sector_count == 1
