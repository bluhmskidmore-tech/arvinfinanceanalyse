from __future__ import annotations

from collections.abc import Sequence

import pytest
from backend.app.core_finance import fresh_trend_watchlist_candidates as fresh_module
from backend.app.core_finance.breakout_geometry import (
    PATTERN_BREAKOUT_LABEL,
    attach_breakout_geometry,
)
from backend.app.core_finance.fresh_trend_watchlist_candidates import (
    FreshTrendWatchlistSnapshot,
    compute_fresh_trend_watchlist_candidates,
)


def test_fresh_trend_float_series_reuses_finite_float_history() -> None:
    history = [10.0, 10.5, 11.0]

    assert fresh_module._float_series(history) is history
    assert fresh_module._float_series([1, "2.5"]) == [1.0, 2.5]
    assert fresh_module._float_series([10.0, float("nan")]) is None


def _snapshot(
    code: str,
    closes: list[float],
    *,
    name: str | None = None,
    sector_name: str = "Electronics",
    amount_ratio: float = 1.4,
    pctchange: float = 0.03,
    turn: float = 8.0,
) -> FreshTrendWatchlistSnapshot:
    amount_history = [1000.0 for _ in closes]
    amount_history[-1] = 1000.0 * amount_ratio
    return FreshTrendWatchlistSnapshot(
        stock_code=code,
        stock_name=name or code,
        sector_code="S1",
        sector_name=sector_name,
        concepts=["Chiplet", "AI hardware"],
        close_value=closes[-1],
        pctchange=pctchange,
        turn=turn,
        amplitude=6.0,
        hlimitedays=0,
        close_history=closes,
        amount_history=amount_history,
    )


@pytest.mark.parametrize(
    (
        "return_20d",
        "return_60d",
        "return_120d",
        "amount_ratio",
        "turn",
        "stock_code",
        "close_to_ma20",
        "expected_score",
    ),
    [
        pytest.param(
            0.90,
            1.60,
            3.20,
            2.50,
            10.0,
            "300001.SZ",
            0.16,
            1.060000,
            id="F1-all-components-at-cap",
        ),
        pytest.param(
            0.08,
            0.18,
            3.20,
            1.00,
            5.0,
            "002001.SZ",
            0.05,
            0.309056,
            id="F2-long-term-surge",
        ),
        pytest.param(
            0.50,
            0.80,
            1.00,
            3.50,
            20.0,
            "688001.SH",
            0.25,
            0.618972,
            id="F3-ratio-upper-and-max-penalty",
        ),
        pytest.param(
            0.30,
            0.60,
            1.00,
            0.70,
            8.0,
            "300002.SZ",
            0.10,
            0.452483,
            id="F4-ratio-lower-bound",
        ),
        pytest.param(
            0.88,
            0.60,
            0.60,
            2.00,
            12.0,
            "301001.SZ",
            0.08,
            0.746361,
            id="F5-short-term-strength",
        ),
        pytest.param(
            0.88,
            0.60,
            0.60,
            2.00,
            12.0,
            "002002.SZ",
            0.08,
            0.686361,
            id="F6-002-board-bonus",
        ),
    ],
)
def test_fresh_trend_watchlist_v2_golden_scores(
    return_20d: float,
    return_60d: float,
    return_120d: float,
    amount_ratio: float,
    turn: float,
    stock_code: str,
    close_to_ma20: float,
    expected_score: float,
) -> None:
    score = fresh_module._score_fresh_trend_watchlist(
        return_20d=return_20d,
        return_60d=return_60d,
        return_120d=return_120d,
        amount_ratio=amount_ratio,
        turn=turn,
        stock_code=stock_code,
        close_to_ma20=close_to_ma20,
    )

    assert round(score, 6) == expected_score


def test_fresh_trend_watchlist_v2_preserves_board_bonus_gap() -> None:
    growth_board_score = fresh_module._score_fresh_trend_watchlist(
        return_20d=0.88,
        return_60d=0.60,
        return_120d=0.60,
        amount_ratio=2.00,
        turn=12.0,
        stock_code="301001.SZ",
        close_to_ma20=0.08,
    )
    small_mid_board_score = fresh_module._score_fresh_trend_watchlist(
        return_20d=0.88,
        return_60d=0.60,
        return_120d=0.60,
        amount_ratio=2.00,
        turn=12.0,
        stock_code="002002.SZ",
        close_to_ma20=0.08,
    )

    assert round(growth_board_score - small_mid_board_score, 6) == 0.060000


def test_fresh_trend_watchlist_selects_high_beta_growth_boards_even_in_overheat() -> None:
    growth_trend = [20.0 + i * 0.23 for i in range(121)]
    mainboard_trend = [20.0 + i * 0.23 for i in range(121)]
    old_sector_trend = [20.0 + i * 0.23 for i in range(121)]
    flat = [20.0 for _ in range(121)]

    result = compute_fresh_trend_watchlist_candidates(
        as_of_date="2026-06-18",
        market_state="OVERHEAT",
        snapshots=[
            _snapshot("300001.SZ", growth_trend, name="Fresh Trend"),
            _snapshot("600001.SH", mainboard_trend, name="Mainboard Old"),
            _snapshot("688001.SH", old_sector_trend, name="Old Sector", sector_name="Banking"),
            _snapshot("301001.SZ", flat, name="Flat Growth"),
        ],
    )

    payload = result.payload
    assert payload["formula_version"] == "rv_fresh_trend_watchlist_candidates_v2"
    assert payload["observation_only"] is True
    assert payload["market_state"] == "OVERHEAT"
    assert payload["candidate_count"] == 1
    assert payload["excluded_stock_count"] == 3

    item = payload["items"][0]
    assert item["rank"] == 1
    assert item["formula_version"] == payload["formula_version"]
    assert item["stock_code"] == "300001.SZ"
    assert item["stock_name"] == "Fresh Trend"
    assert item["sector_name"] == "Electronics"
    assert item["concepts"] == ["Chiplet", "AI hardware"]
    assert item["return_20d"] >= 0.08
    assert item["return_60d"] >= 0.18
    assert item["return_120d"] >= 0.30
    assert item["score"] == 0.372170


def test_fresh_trend_watchlist_excludes_chinese_old_economy_sectors() -> None:
    growth_trend = [20.0 + i * 0.23 for i in range(121)]

    result = compute_fresh_trend_watchlist_candidates(
        as_of_date="2026-06-18",
        market_state="OVERHEAT",
        snapshots=[
            _snapshot("300002.SZ", growth_trend, name="Bank Growth", sector_name="银行"),
        ],
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["excluded_stock_count"] == 1


def test_fresh_trend_watchlist_pauses_when_market_has_no_tradable_trend() -> None:
    snapshots = [_snapshot("300001.SZ", [20.0 + i * 0.23 for i in range(121)])]

    result = compute_fresh_trend_watchlist_candidates(
        as_of_date="2026-06-18",
        market_state="NO_DATA",
        snapshots=snapshots,
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["input_stock_count"] == 1
    assert result.payload["excluded_stock_count"] == 1


def test_fresh_trend_watchlist_normalizes_history_once_for_late_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_float_series = fresh_module._float_series
    call_count = 0

    def counted_float_series(values: Sequence[object]) -> list[float] | None:
        nonlocal call_count
        call_count += 1
        return original_float_series(values)

    monkeypatch.setattr(fresh_module, "_float_series", counted_float_series)
    result = compute_fresh_trend_watchlist_candidates(
        as_of_date="2026-06-18",
        market_state="OVERHEAT",
        snapshots=[_snapshot("301010.SZ", [20.0] * 121, name="Flat Growth Reject")],
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["excluded_stock_count"] == 1
    assert result.payload["insufficient_history_count"] == 0
    assert call_count == 2


def test_fresh_trend_watchlist_counts_short_history_even_when_board_is_excluded() -> None:
    result = compute_fresh_trend_watchlist_candidates(
        as_of_date="2026-06-18",
        market_state="OVERHEAT",
        snapshots=[_snapshot("600011.SH", [20.0] * 20, name="Mainboard Short")],
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["excluded_stock_count"] == 1
    assert result.payload["insufficient_history_count"] == 1


# ---- 观察位几何（attach_breakout_geometry）golden 样本 -----------------------


def _computed_fresh_trend_payload() -> dict[str, object]:
    """跑真实 compute 生成 2 只成长板候选（同一趋势序列，close 均为 50.0）。"""
    growth_trend = [20.0 + i * 0.25 for i in range(121)]
    return compute_fresh_trend_watchlist_candidates(
        as_of_date="2026-06-18",
        market_state="WARM",
        snapshots=[
            _snapshot("300001.SZ", growth_trend, name="Fresh A"),
            _snapshot("301001.SZ", list(growth_trend), name="Fresh B"),
        ],
    ).payload


def test_fresh_trend_watchlist_breakout_geometry_golden_keeps_own_close_and_fills_missing() -> None:
    """golden：新趋势候选自带策略日 close(50.0)不被覆盖，几何只补
    breakout_level/distance/pattern；缺 K 线候选三字段保持 None(而非 0)且
    close 仍保留自身值；原 payload 不被回写。"""
    payload = _computed_fresh_trend_payload()
    assert payload["candidate_count"] == 2

    attached = attach_breakout_geometry(
        payload,
        close_history_by_code={"300001.SZ": [40.0] * 55 + [50.0]},
        price_as_of_date="2026-06-18",
        last_trade_date_by_code={"300001.SZ": "2026-06-18"},
    )
    by_code = {str(item["stock_code"]): item for item in attached["items"]}

    geometry_item = by_code["300001.SZ"]
    assert geometry_item["close"] == 50.0
    assert geometry_item["breakout_level"] == 40.0
    assert geometry_item["distance_to_breakout_pct"] == 25.0
    assert geometry_item["pattern"] == PATTERN_BREAKOUT_LABEL
    assert "price_as_of_date" not in geometry_item
    assert "price_stale" not in geometry_item

    missing_item = by_code["301001.SZ"]
    assert missing_item["close"] == 50.0
    assert missing_item["breakout_level"] is None
    assert missing_item["distance_to_breakout_pct"] is None
    assert missing_item["pattern"] is None

    original_by_code = {str(item["stock_code"]): item for item in payload["items"]}
    for stock_code, item in by_code.items():
        assert item["score"] == original_by_code[stock_code]["score"]
        assert item["concepts"] == original_by_code[stock_code]["concepts"]
    for original_item in payload["items"]:
        assert "pattern" not in original_item
        assert "breakout_level" not in original_item
    assert "breakout_geometry" not in payload
    assert attached["breakout_geometry"]["price_as_of_date"] == "2026-06-18"


def test_fresh_trend_watchlist_breakout_geometry_golden_fails_closed_on_close_conflict() -> None:
    """golden：几何 close 与候选自带 close 不等(同股同日不同价)时该行几何
    fail-closed 保持 None，close 保留原值，不加停牌披露字段。"""
    payload = _computed_fresh_trend_payload()

    attached = attach_breakout_geometry(
        payload,
        close_history_by_code={"300001.SZ": [40.0] * 55 + [49.75]},
        price_as_of_date="2026-06-18",
    )
    item = {str(row["stock_code"]): row for row in attached["items"]}["300001.SZ"]

    assert item["close"] == 50.0
    assert item["breakout_level"] is None
    assert item["distance_to_breakout_pct"] is None
    assert item["pattern"] is None
    assert "price_as_of_date" not in item
    assert "price_stale" not in item
