from __future__ import annotations

from collections.abc import Sequence

import pytest
from backend.app.core_finance import fresh_trend_watchlist_candidates as fresh_module
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
