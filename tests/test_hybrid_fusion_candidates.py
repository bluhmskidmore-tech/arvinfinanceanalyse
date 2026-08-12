from __future__ import annotations

import math
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
    assert items[0]["fusion_action"] == "monitor_only"
    assert items[0]["trade_eligible"] is False
    assert items[0]["cycle_score_status"] == "macro_pending"
    assert items[0]["block_reason"] == "macro_score_missing"
    assert items[0]["attention_score"] > 0
    assert items[0]["price_confirm_score"] > 0
    assert items[0]["confidence"] == "high"
    assert set(items[0]["evidence"]["source_kinds"]) == {"stock_candidate", "factor_screen", "theme_breakout"}
    assert items[0]["evidence"]["cycle_score_status"] == "macro_pending"
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


def test_hybrid_fusion_discloses_pool_percentile_threshold_basis_and_lifecourt_scale() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801080", "rank": 1}]},
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "A",
                    "sector_code": "801080",
                    "close_strength": 0.95,
                    "abnormal_turnover": 1.5,
                    "breakout_extension_norm": 0.12,
                },
                {
                    "rank": 2,
                    "stock_code": "000001.SZ",
                    "stock_name": "B",
                    "sector_code": "801080",
                    "close_strength": 0.55,
                    "abnormal_turnover": 1.2,
                    "breakout_extension_norm": 0.12,
                },
            ]
        },
        factor_screen_payload=None,
        theme_breakout_payload=None,
    )

    payload = result.payload
    assert payload["threshold_basis"] == "same_day_candidate_pool_percentile_plus_abs_floor"
    items = cast(list[dict[str, Any]], payload["items"])
    for item in items:
        basis = item["evidence"]["threshold_basis"]
        assert basis["kind"] == "same_day_candidate_pool_percentile_plus_abs_floor"
        assert basis["candidate_pool_size"] == 2
        assert "absolute" in str(basis["note"])
        scale = item["evidence"]["lifecourt_score_scale"]
        assert scale["positive_weight_sum"] == 0.84
        assert scale["normalized"] is True
        assert scale["theoretical_max"] == 1.0
        contribution = scale["effective_max_fusion_contribution"]
        assert contribution["cycle"] == 0.65
        assert contribution["lifecourt"] == 0.35


def test_hybrid_fusion_threshold_basis_disclosed_on_empty_payloads_too() -> None:
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="OVERHEAT",
        sector_rank_payload=None,
        stock_candidates_payload=None,
        factor_screen_payload=None,
        theme_breakout_payload=None,
    )
    assert result.payload["threshold_basis"] == "same_day_candidate_pool_percentile_plus_abs_floor"


def test_safe_int_rejects_non_integer_values() -> None:
    from backend.app.core_finance.hybrid_fusion_candidates import _safe_int

    assert _safe_int(3) == 3
    assert _safe_int(3.0) == 3
    assert _safe_int("3") == 3
    assert _safe_int(" 3 ") == 3
    # Rank/event-count fields are integer-semantic: a fractional value signals an
    # upstream data anomaly and must be rejected instead of silently truncated.
    assert _safe_int(2.9) is None
    assert _safe_int("2.9") is None
    assert _safe_int(-1.5) is None
    assert _safe_int(None) is None
    assert _safe_int("abc") is None


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
    assert without_macro["fusion_action"] == "monitor_only"
    assert without_macro["block_reason"] == "macro_score_missing"
    assert with_macro["cycle_score_status"] == "macro_landed"
    assert with_macro["block_reason"] is None
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


def test_hybrid_fusion_cycle_score_renormalizes_when_factor_screen_coverage_missing() -> None:
    # Two symmetric stocks (identical macro/sector/price-confirm inputs). One has a real,
    # worst-possible factor_screen rank (factor_rank_score == 0.0 but row is present); the
    # other is entirely absent from factor_screen (row is None, i.e. a data coverage gap).
    # Both must NOT collapse to the same cycle_score: only the coverage-gap stock should
    # have its remaining weights renormalized, the genuinely-worst-ranked stock keeps the
    # unrenormalized (lower) formula.
    common_kwargs = dict(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801080", "rank": 1}]},
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "HasWorstFactorRank",
                    "sector_code": "801080",
                    "close_strength": 0.9,
                    "abnormal_turnover": 1.6,
                    "breakout_extension_norm": 0.12,
                },
                {
                    "rank": 2,
                    "stock_code": "688002.SH",
                    "stock_name": "NoFactorCoverage",
                    "sector_code": "801080",
                    "close_strength": 0.9,
                    "abnormal_turnover": 1.6,
                    "breakout_extension_norm": 0.12,
                },
            ]
        },
        factor_screen_payload={
            "items": [
                {"rank": 1, "stock_code": "999999.SH", "stock_name": "Other"},
                {"rank": 2, "stock_code": "688001.SH", "stock_name": "HasWorstFactorRank"},
            ]
        },
        theme_breakout_payload=None,
    )

    with_macro = {
        item["stock_code"]: item
        for item in compute_hybrid_fusion_candidates(macro_score=0.5, **common_kwargs).payload["items"]
    }
    worst_rank_item = with_macro["688001.SH"]
    missing_item = with_macro["688002.SH"]

    assert worst_rank_item["evidence"]["factor_rank_available"] is True
    assert missing_item["evidence"]["factor_rank_available"] is False
    assert worst_rank_item["evidence"]["factor_rank_score"] == 0.0
    assert missing_item["evidence"]["factor_rank_score"] == 0.0

    # macro-landed weights: 0.30 macro + 0.35 industry + 0.20 flow + 0.15 valuation.
    # Missing coverage renormalizes over the remaining 0.85 weight instead of eating a
    # silent 0.15*0 penalty.
    assert math.isclose(missing_item["cycle_score"], worst_rank_item["cycle_score"] / 0.85, abs_tol=1e-5)
    assert missing_item["cycle_score"] > worst_rank_item["cycle_score"]

    without_macro = {
        item["stock_code"]: item
        for item in compute_hybrid_fusion_candidates(macro_score=None, **common_kwargs).payload["items"]
    }
    legacy_worst_rank_item = without_macro["688001.SH"]
    legacy_missing_item = without_macro["688002.SH"]

    assert legacy_worst_rank_item["evidence"]["factor_rank_available"] is True
    assert legacy_missing_item["evidence"]["factor_rank_available"] is False

    # legacy (macro pending) weights: 0.70 sector + 0.30 factor; renormalize over 0.70.
    assert math.isclose(
        legacy_missing_item["cycle_score"], legacy_worst_rank_item["cycle_score"] / 0.70, abs_tol=1e-5
    )
    assert legacy_missing_item["cycle_score"] > legacy_worst_rank_item["cycle_score"]


def test_hybrid_fusion_does_not_renormalize_when_factor_rank_is_genuinely_low() -> None:
    # A stock present in factor_screen with the worst rank keeps the standard (lower)
    # formula: real low scores are not entitled to renormalization, only missing coverage is.
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801080", "rank": 1}]},
        stock_candidates_payload={
            "items": [
                {
                    "rank": 1,
                    "stock_code": "688001.SH",
                    "stock_name": "WorstFactorRank",
                    "sector_code": "801080",
                    "close_strength": 0.9,
                    "abnormal_turnover": 1.6,
                    "breakout_extension_norm": 0.12,
                }
            ]
        },
        factor_screen_payload={
            "items": [
                {"rank": 1, "stock_code": "999999.SH", "stock_name": "Other"},
                {"rank": 2, "stock_code": "688001.SH", "stock_name": "WorstFactorRank"},
            ]
        },
        theme_breakout_payload=None,
        macro_score=0.5,
    )
    item = cast(list[dict[str, Any]], result.payload["items"])[0]
    assert item["stock_code"] == "688001.SH"
    assert item["evidence"]["factor_rank_available"] is True
    assert item["evidence"]["factor_rank_score"] == 0.0
    expected = 0.30 * 0.5 + 0.35 * 1.0 + 0.20 * item["price_confirm_score"] + 0.15 * 0.0
    assert math.isclose(item["cycle_score"], expected, rel_tol=1e-9)


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


def test_hybrid_fusion_formula_version_is_v5_after_theme_v6_input_break() -> None:
    # v5 断代原因：theme_breakout v5→v6 七篮子使 theme 输入面从约 33 只扩到
    # 1500+ 只，同版本号不得跨输入代际聚合。
    assert FORMULA_VERSION == "rv_hybrid_fusion_candidates_v5"


def test_hybrid_fusion_lifecourt_score_is_normalized_to_unit_scale() -> None:
    from backend.app.core_finance.hybrid_fusion_candidates import _lifecourt_proxy_score

    # All positive components at 1.0 and zero crowding -> raw sum 0.84 -> normalized 1.0.
    assert math.isclose(
        _lifecourt_proxy_score(
            vcov_score=1.0,
            consensus_score=1.0,
            burst_score=1.0,
            price_confirm_score=1.0,
            crowding_score=0.0,
            hygiene_score=1.0,
            regime_score=1.0,
        ),
        1.0,
        rel_tol=1e-9,
    )


def test_hybrid_fusion_absolute_floor_blocks_strong_action_in_weak_pool() -> None:
    """A tiny weak pool must not mint core_plus_trading via percentile alone."""
    from backend.app.core_finance.hybrid_fusion_config import HybridFusionThresholds

    weak_items = [
        {
            "rank": idx,
            "stock_code": f"00000{idx}.SZ",
            "stock_name": f"Weak{idx}",
            "sector_code": "801780",
            "sector_name": "Bank",
            "sector_rank": 8,
            "close_strength": 0.15,
            "abnormal_turnover": 1.05,
            "breakout_extension_norm": 0.12,
        }
        for idx in range(1, 4)
    ]
    result = compute_hybrid_fusion_candidates(
        as_of_date="2026-05-08",
        market_state="HOT",
        sector_rank_payload={"items": [{"sector_code": "801780", "rank": 8}]},
        stock_candidates_payload={"items": weak_items},
        factor_screen_payload=None,
        theme_breakout_payload=None,
        macro_score=0.2,
        thresholds=HybridFusionThresholds(
            stance_strong_q=0.50,  # make relative "strong" easy in a 3-name pool
            stance_neutral_q=0.30,
            stance_cycle_strong_abs_min=0.35,
            stance_life_strong_abs_min=0.35,
        ),
    )
    items = cast(list[dict[str, Any]], result.payload["items"])
    assert items
    assert all(item["fusion_action"] != "core_plus_trading" for item in items)
    assert all(float(item["lifecourt_proxy_score"]) < 0.35 for item in items)
