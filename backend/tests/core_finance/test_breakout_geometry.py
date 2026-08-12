from __future__ import annotations

import json
from typing import Any, cast

from backend.app.core_finance.breakout_geometry import (
    BREAKOUT_GEOMETRY_MIN_HISTORY,
    PATTERN_BREAKOUT_LABEL,
    PATTERN_PULLBACK_LABEL,
    attach_breakout_geometry,
)
from backend.app.core_finance.fresh_trend_watchlist_candidates import (
    FreshTrendWatchlistSnapshot,
    compute_fresh_trend_watchlist_candidates,
)
from backend.app.core_finance.hybrid_fusion_candidates import (
    compute_hybrid_fusion_candidates,
)
from backend.app.core_finance.livermore_stock_candidates import (
    StockCandidateSnapshot,
    compute_stock_candidates,
)
from backend.app.core_finance.mean_reversion_candidates import (
    MeanReversionSnapshot,
    compute_mean_reversion_candidates,
)
from backend.app.core_finance.uptrend_momentum_candidates import (
    UptrendMomentumSnapshot,
    compute_uptrend_momentum_candidates,
)

AS_OF = "2026-05-27"


def _flat_history(prior_close: float, last_close: float) -> list[float]:
    """55 个先导收盘全为 prior_close + 1 个信号日收盘，长度恰为最小窗口 56。"""
    return [prior_close] * (BREAKOUT_GEOMETRY_MIN_HISTORY - 1) + [last_close]


def _geometry_tuple(item: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        item["close"],
        item["breakout_level"],
        item["distance_to_breakout_pct"],
        item["pattern"],
    )


def _items_by_code(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["stock_code"]): item for item in cast(list[dict[str, Any]], payload["items"])}


# ---- hybrid_fusion 观察位几何 golden（融合 items 自身不带价格字段） ----------


def _computed_fusion_payload(stock_codes: list[str]) -> dict[str, Any]:
    """跑真实 compute_hybrid_fusion_candidates，以多因子候选为唯一融合来源。"""
    factor_payload = {
        "items": [
            {"rank": index, "stock_code": code, "stock_name": f"Fusion{index}"}
            for index, code in enumerate(stock_codes, start=1)
        ]
    }
    return cast(
        dict[str, Any],
        compute_hybrid_fusion_candidates(
            as_of_date=AS_OF,
            market_state="WARM",
            sector_rank_payload=None,
            stock_candidates_payload=None,
            factor_screen_payload=factor_payload,
            theme_breakout_payload=None,
            macro_score=None,
        ).payload,
    )


def test_hybrid_fusion_breakout_geometry_golden_fills_fields_and_keeps_missing_none() -> None:
    """golden：融合候选补几何（突破档）；缺 K 线候选四字段保持 None(而非 0)；
    融合自身评分字段不被改写；原 payload 不被回写。"""
    payload = _computed_fusion_payload(["600100.SH", "600200.SH"])
    assert payload["candidate_count"] == 2
    original_scores = {
        str(item["stock_code"]): item["fusion_score"]
        for item in cast(list[dict[str, Any]], payload["items"])
    }

    attached = attach_breakout_geometry(
        payload,
        close_history_by_code={"600100.SH": _flat_history(100.0, 103.0)},
        price_as_of_date=AS_OF,
    )
    by_code = _items_by_code(attached)

    filled = by_code["600100.SH"]
    assert filled["close"] == 103.0
    assert filled["breakout_level"] == 100.0
    assert filled["distance_to_breakout_pct"] == 3.0
    assert filled["pattern"] == PATTERN_BREAKOUT_LABEL
    assert "price_as_of_date" not in filled
    assert "price_stale" not in filled

    missing = by_code["600200.SH"]
    assert missing["close"] is None
    assert missing["breakout_level"] is None
    assert missing["distance_to_breakout_pct"] is None
    assert missing["pattern"] is None

    for code, item in by_code.items():
        assert item["fusion_score"] == original_scores[code]

    geometry = cast(dict[str, Any], attached["breakout_geometry"])
    assert geometry["price_as_of_date"] == AS_OF
    assert geometry["breakout_basis"] == "prior_55d_close_high"
    assert geometry["distance_basis"] == "close_over_breakout_minus_one_pct"

    for original_item in cast(list[dict[str, Any]], payload["items"]):
        assert "pattern" not in original_item
        assert "close" not in original_item
    assert "breakout_geometry" not in payload

    serialized = json.dumps(attached, allow_nan=False, ensure_ascii=False)
    assert "NaN" not in serialized


def test_hybrid_fusion_breakout_geometry_golden_discloses_stale_price_anchor() -> None:
    """golden：融合候选无自带 close，停牌披露语义与多因子候选一致——历史末日
    早于策略日时补 price_as_of_date + price_stale；末日等于策略日不加字段；
    无几何值的候选即使日期滞后也不加字段。"""
    payload = _computed_fusion_payload(["600100.SH", "600300.SH", "600400.SH"])

    attached = attach_breakout_geometry(
        payload,
        close_history_by_code={
            "600100.SH": _flat_history(100.0, 103.0),
            "600300.SH": _flat_history(100.0, 98.0),
        },
        price_as_of_date=AS_OF,
        last_trade_date_by_code={
            "600100.SH": AS_OF,
            "600300.SH": "2026-05-20",
            "600400.SH": "2026-05-20",
        },
    )
    by_code = _items_by_code(attached)

    fresh_item = by_code["600100.SH"]
    assert "price_as_of_date" not in fresh_item
    assert "price_stale" not in fresh_item

    suspended_item = by_code["600300.SH"]
    assert suspended_item["price_as_of_date"] == "2026-05-20"
    assert suspended_item["price_stale"] is True
    assert suspended_item["close"] == 98.0
    assert suspended_item["pattern"] == PATTERN_PULLBACK_LABEL

    missing_item = by_code["600400.SH"]
    assert missing_item["close"] is None
    assert "price_as_of_date" not in missing_item
    assert "price_stale" not in missing_item


# ---- 跨源一致性：同股同策略日出现在多个源时几何逐位一致 ----------------------


def _uptrend_snapshot(code: str, closes: list[float], *, sector_code: str) -> UptrendMomentumSnapshot:
    amounts = [1000.0 for _ in closes]
    amounts[-1] = 1300.0
    return UptrendMomentumSnapshot(
        stock_code=code,
        stock_name=f"Momentum {code}",
        sector_code=sector_code,
        sector_name=sector_code,
        close_value=closes[-1],
        pctchange=0.02,
        turn=1.5,
        amplitude=3.0,
        close_history=closes,
        amount_history=amounts,
    )


def _fresh_snapshot(code: str, closes: list[float]) -> FreshTrendWatchlistSnapshot:
    amounts = [1000.0 for _ in closes]
    amounts[-1] = 1400.0
    return FreshTrendWatchlistSnapshot(
        stock_code=code,
        stock_name=f"Fresh {code}",
        sector_code="S9",
        sector_name="Electronics",
        concepts=["AI hardware"],
        close_value=closes[-1],
        pctchange=0.03,
        turn=8.0,
        amplitude=6.0,
        hlimitedays=0,
        close_history=closes,
        amount_history=amounts,
    )


def _mean_reversion_snapshot(code: str, closes: list[float]) -> MeanReversionSnapshot:
    volumes = [1_000_000.0] * (len(closes) - 1) + [2_000_000.0]
    return MeanReversionSnapshot(
        stock_code=code,
        stock_name=f"Reversion {code}",
        sector_code="S5",
        sector_name="SectorB",
        close_value=closes[-1],
        low_value=70.0,
        high_value=74.5,
        volume=volumes[-1],
        close_history=closes,
        volume_history=volumes,
    )


def _crash_bounce_series() -> list[float]:
    """70 根：40 根平台 100 -> 20 根阴跌至 66 -> 尾部 10 根企稳回升至 74。
    满足超跌门控（dd60=-26%、close>ma5>ma10、量比 2.0、收盘强度 0.89）。"""
    plateau = [100.0] * 40
    decline = [100.0 - 1.7 * (i + 1) for i in range(20)]
    rebound = [66.0, 67.0, 68.0, 69.0, 70.0, 70.0, 71.0, 72.0, 73.0, 74.0]
    return plateau + decline + rebound


def test_breakout_geometry_is_bitwise_identical_across_candidate_sources() -> None:
    """同一只股票、同一策略日、同一份收盘序列：动量/新趋势/超跌/融合各源
    attach 后的 close/breakout_level/distance/pattern 逐位一致，且与
    Livermore 候选自身的 breakout 字段对拍相等（单一公式实现的行为锁）。"""
    growth_code = "300100.SZ"
    reversion_code = "600200.SH"
    livermore_code = "600100.SH"
    growth_closes = [20.0 + i * 0.25 for i in range(130)]
    reversion_closes = _crash_bounce_series()
    livermore_closes = [100.0 + 0.5 * i for i in range(130)]
    history_map = {
        growth_code: growth_closes,
        reversion_code: reversion_closes,
        livermore_code: livermore_closes,
    }

    momentum_payload = cast(
        dict[str, Any],
        compute_uptrend_momentum_candidates(
            as_of_date=AS_OF,
            market_state="WARM",
            snapshots=[
                _uptrend_snapshot(growth_code, growth_closes, sector_code="S1"),
                _uptrend_snapshot(livermore_code, livermore_closes, sector_code="S2"),
            ],
        ).payload,
    )
    fresh_payload = cast(
        dict[str, Any],
        compute_fresh_trend_watchlist_candidates(
            as_of_date=AS_OF,
            market_state="WARM",
            snapshots=[_fresh_snapshot(growth_code, growth_closes)],
        ).payload,
    )
    reversion_payload = cast(
        dict[str, Any],
        compute_mean_reversion_candidates(
            as_of_date=AS_OF,
            market_state="WARM",
            snapshots=[_mean_reversion_snapshot(reversion_code, reversion_closes)],
        ).payload,
    )
    fusion_payload = _computed_fusion_payload([growth_code, reversion_code, livermore_code])
    livermore_payload = cast(
        dict[str, Any],
        compute_stock_candidates(
            as_of_date=AS_OF,
            market_state="WARM",
            snapshots=[
                StockCandidateSnapshot(
                    stock_code=livermore_code,
                    stock_name="Consistency",
                    sector_code="801080",
                    sector_name="电子",
                    sector_rank=2,
                    open_value=livermore_closes[-2],
                    high_value=livermore_closes[-1],
                    low_value=livermore_closes[-2],
                    close_value=livermore_closes[-1],
                    turnover_free=4.0,
                    limit_ratio=0.1,
                    close_history=livermore_closes,
                    turnover_history=[1.0] * len(livermore_closes),
                )
            ],
        ).payload,
    )

    assert momentum_payload["candidate_count"] == 2
    assert fresh_payload["candidate_count"] == 1
    assert reversion_payload["candidate_count"] == 1
    assert fusion_payload["candidate_count"] == 3
    livermore_items = cast(list[dict[str, Any]], livermore_payload["items"])
    assert len(livermore_items) == 1
    livermore_item = livermore_items[0]

    attached_by_source = {
        source: _items_by_code(
            attach_breakout_geometry(
                payload,
                close_history_by_code=history_map,
                price_as_of_date=AS_OF,
            )
        )
        for source, payload in (
            ("uptrend_momentum", momentum_payload),
            ("fresh_trend_watchlist", fresh_payload),
            ("mean_reversion", reversion_payload),
            ("hybrid_fusion", fusion_payload),
        )
    }

    growth_tuples = {
        source: _geometry_tuple(items[growth_code])
        for source, items in attached_by_source.items()
        if growth_code in items
    }
    assert set(growth_tuples) == {"uptrend_momentum", "fresh_trend_watchlist", "hybrid_fusion"}
    assert len(set(growth_tuples.values())) == 1
    growth_close, growth_breakout, growth_distance, growth_pattern = next(iter(growth_tuples.values()))
    assert growth_close == round(growth_closes[-1], 6)
    assert growth_breakout == round(growth_closes[-2], 6)
    assert growth_distance == round((growth_close - growth_breakout) / growth_breakout * 100.0, 4)
    assert growth_pattern == PATTERN_BREAKOUT_LABEL

    reversion_tuples = {
        source: _geometry_tuple(items[reversion_code])
        for source, items in attached_by_source.items()
        if reversion_code in items
    }
    assert set(reversion_tuples) == {"mean_reversion", "hybrid_fusion"}
    assert len(set(reversion_tuples.values())) == 1
    assert next(iter(reversion_tuples.values())) == (74.0, 100.0, -26.0, PATTERN_PULLBACK_LABEL)

    livermore_tuples = {
        source: _geometry_tuple(items[livermore_code])
        for source, items in attached_by_source.items()
        if livermore_code in items
    }
    assert set(livermore_tuples) == {"uptrend_momentum", "hybrid_fusion"}
    assert len(set(livermore_tuples.values())) == 1
    close_value, breakout_level, distance, pattern = next(iter(livermore_tuples.values()))
    assert close_value == livermore_item["close"]
    assert breakout_level == livermore_item["breakout_level"]
    livermore_close = cast(float, livermore_item["close"])
    livermore_breakout = cast(float, livermore_item["breakout_level"])
    assert distance == round((livermore_close - livermore_breakout) / livermore_breakout * 100.0, 4)
    assert pattern == PATTERN_BREAKOUT_LABEL
