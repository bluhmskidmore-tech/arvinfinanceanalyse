from __future__ import annotations

from typing import Any, cast

from backend.app.core_finance.hybrid_fusion_candidates import (
    FORMULA_VERSION,
    compute_hybrid_fusion_candidates,
)


def test_hybrid_fusion_scores_dedupes_and_orders_existing_signal_sources() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={
            "items": [
                {"sector_code": "801080", "sector_name": "Electronic", "rank": 1},
                {"sector_code": "801780", "sector_name": "Bank", "rank": 3},
            ]
        },
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Alpha Semi",
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                    "sector_rank": 1,
                    "close_strength": 0.98,
                    "abnormal_turnover": 1.8,
                    "breakout_extension_norm": 0.12,
                    "closed_up_limit": False,
                },
                {
                    "rank": 2,
                    "stock_code": "000001.SZ",
                    "stock_name": "Bank Alpha",
                    "sector_code": "801780",
                    "sector_name": "Bank",
                    "sector_rank": 3,
                    "close_strength": 0.99,
                    "abnormal_turnover": 3.1,
                    "breakout_extension_norm": 0.2,
                    "closed_up_limit": True,
                },
            ]
        },
        factor_screen_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Alpha Semi",
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                    "score": 0.88,
                },
                {
                    "rank": 2,
                    "stock_code": "300001.SZ",
                    "stock_name": "Beta Growth",
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                    "score": 0.76,
                },
            ]
        },
        theme_breakout_payload={
            "items": [
                {
                    "rank": 1,
                    "theme_key": "concept:C001",
                    "theme_name": "Chiplet",
                    "movement_event_count": 3,
                    "items": [
                        {
                            "stock_code": "688001.SH",
                            "stock_name": "Alpha Semi",
                            "sector_code": "801080",
                            "sector_name": "Electronic",
                            "sector_rank": 1,
                            "pctchange": 10.2,
                            "turn": 5.1,
                            "close_strength": 0.97,
                            "closed_up_limit": True,
                            "movement_event_count": 2,
                        },
                        {
                            "stock_code": "300001.SZ",
                            "stock_name": "Beta Growth",
                            "sector_code": "801080",
                            "sector_name": "Electronic",
                            "sector_rank": 1,
                            "pctchange": 6.2,
                            "turn": 3.2,
                            "close_strength": 0.86,
                            "closed_up_limit": False,
                            "movement_event_count": 1,
                        },
                    ],
                }
            ]
        },
    )

    payload = result.payload
    assert payload["as_of_date"] == "2026-05-08"
    assert payload["formula_version"] == FORMULA_VERSION
    assert payload["observation_only"] is True
    assert payload["candidate_count"] == 3

    items = cast(list[dict[str, Any]], payload["items"])
    assert [item["stock_code"] for item in items] == ["688001.SH", "300001.SZ", "000001.SZ"]
    assert items[0]["rank"] == 1
    assert items[0]["fusion_score"] > items[1]["fusion_score"] > items[2]["fusion_score"]
    assert items[0]["cycle_score"] > 0
    assert items[0]["lifecourt_proxy_score"] > 0
    assert items[0]["vcov_score"] == items[0]["attention_score"]
    assert items[0]["consensus_score"] == 1.0
    assert items[0]["life_long_pass"] is True
    assert items[0]["fusion_action"] in {"core_plus_trading", "core_reduce_trading", "satellite_trial"}
    assert items[0]["attention_score"] > 0
    assert items[0]["price_confirm_score"] > 0
    assert items[0]["confidence"] == "high"
    assert set(items[0]["evidence"]["source_kinds"]) == {"stock_candidate", "factor_screen", "theme_breakout"}
    assert items[2]["crowding_penalty"] > 0
    assert "observation-only" in str(payload).lower()
    assert "buy" not in str(payload).lower()
    assert "order" not in str(payload).lower()


def test_hybrid_fusion_applies_report_lifecourt_formula_and_life_long_gates() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801080", "rank": 1}]},
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Strong",
                    "sector_code": "801080",
                    "close_strength": 0.95,
                    "abnormal_turnover": 1.5,
                    "breakout_extension_norm": 0.12,
                },
                {
                    "rank": 2,
                    "stock_code": "000001.SZ",
                    "stock_name": "Crowded",
                    "sector_code": "801080",
                    "close_strength": 0.4,
                    "abnormal_turnover": 4.2,
                    "breakout_extension_norm": 0.4,
                    "closed_up_limit": True,
                },
            ]
        },
        factor_screen_payload={
            "items": [
                {"rank": 1, "stock_code": "688001.SH", "stock_name": "Strong", "sector_code": "801080"},
                {"rank": 2, "stock_code": "000001.SZ", "stock_name": "Crowded", "sector_code": "801080"},
            ]
        },
        theme_breakout_payload=None,
    )

    items = cast(list[dict[str, Any]], result.payload["items"])
    assert result.payload["formula_version"] == FORMULA_VERSION
    assert items[0]["stock_code"] == "688001.SH"
    assert items[0]["life_long_pass"] is True
    assert items[1]["life_long_pass"] is False
    assert "0.18*VCOV" in str(items[0]["evidence"]["lifecourt_formula"])


def test_hybrid_fusion_uses_macro_score_when_landed() -> None:
    common_kwargs = {
        "as_of_date": "2026-05-08",
        "market_state": "HOT",
        "sector_rank_payload": {"items": [{"sector_code": "801080", "rank": 1}]},
        "stock_candidates_payload": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Alpha",
                    "sector_code": "801080",
                    "close_strength": 0.9,
                    "abnormal_turnover": 1.6,
                    "breakout_extension_norm": 0.12,
                }
            ]
        },
        "factor_screen_payload": {
            "items": [{"rank": 1, "stock_code": "688001.SH", "stock_name": "Alpha", "sector_code": "801080"}]
        },
        "theme_breakout_payload": None,
    }
    without_macro = compute_hybrid_fusion_candidates(macro_score=None, **common_kwargs).payload["items"][0]
    with_macro = compute_hybrid_fusion_candidates(macro_score=0.2, **common_kwargs).payload["items"][0]
    assert without_macro["cycle_score"] != with_macro["cycle_score"]
    assert str(with_macro["evidence"]["cycle_formula"]).startswith("0.30 Macro")


def test_hybrid_fusion_stays_empty_outside_warm_or_hot_market_state() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="OVERHEAT",
        sector_rank_payload={"items": [{"sector_code": "801080", "rank": 1}]},
        stock_candidates_payload={"items": [{"stock_code": "688001.SH", "stock_name": "Alpha", "rank": 1}]},
        factor_screen_payload=None,
        theme_breakout_payload=None,
    )

    payload = result.payload
    assert payload["candidate_count"] == 0
    assert payload["items"] == []
    assert "inactive for market_state OVERHEAT" in payload["coverage_note"]


def test_hybrid_fusion_stays_empty_when_market_state_is_pending_data() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="PENDING_DATA",
        sector_rank_payload={"items": [{"sector_code": "801080", "rank": 1}]},
        stock_candidates_payload={"items": [{"stock_code": "688001.SH", "stock_name": "Alpha", "rank": 1}]},
        factor_screen_payload=None,
        theme_breakout_payload=None,
    )

    payload = result.payload
    assert payload["candidate_count"] == 0
    assert payload["items"] == []
    assert "inactive for market_state PENDING_DATA" in payload["coverage_note"]


def test_hybrid_fusion_reports_missing_candidate_sources() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="WARM",
        sector_rank_payload=None,
        stock_candidates_payload=None,
        factor_screen_payload={"items": []},
        theme_breakout_payload=None,
    )

    payload = result.payload
    assert payload["candidate_count"] == 0
    assert payload["items"] == []
    assert payload["coverage_note"] == "No usable hybrid fusion candidate sources."


def test_hybrid_fusion_uses_sector_from_factor_source_when_trend_source_lacks_it() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801080", "sector_name": "Electronic", "rank": 1}]},
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Alpha Semi",
                    "close_strength": 0.9,
                    "abnormal_turnover": 1.6,
                    "breakout_extension_norm": 0.12,
                }
            ]
        },
        factor_screen_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Alpha Semi",
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                    "score": 0.88,
                }
            ]
        },
        theme_breakout_payload=None,
    )

    item = cast(list[dict[str, Any]], result.payload["items"])[0]
    assert item["sector_code"] == "801080"
    assert item["sector_name"] == "Electronic"
    assert item["cycle_score"] == 1.0
    assert item["evidence"]["sector_rank"] == 1


def test_hybrid_fusion_uses_name_from_factor_source_when_trend_source_lacks_it() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801080", "sector_name": "Electronic", "rank": 1}]},
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                    "close_strength": 0.9,
                    "abnormal_turnover": 1.6,
                    "breakout_extension_norm": 0.12,
                }
            ]
        },
        factor_screen_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "Alpha Semi",
                    "sector_code": "801080",
                    "sector_name": "Electronic",
                    "score": 0.88,
                }
            ]
        },
        theme_breakout_payload=None,
    )

    item = cast(list[dict[str, Any]], result.payload["items"])[0]
    assert item["stock_name"] == "Alpha Semi"
