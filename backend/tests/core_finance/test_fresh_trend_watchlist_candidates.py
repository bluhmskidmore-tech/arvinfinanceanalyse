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
    assert payload["formula_version"] == "rv_fresh_trend_watchlist_candidates_v1"
    assert payload["observation_only"] is True
    assert payload["market_state"] == "OVERHEAT"
    assert payload["candidate_count"] == 1
    assert payload["excluded_stock_count"] == 3

    item = payload["items"][0]
    assert item["rank"] == 1
    assert item["stock_code"] == "300001.SZ"
    assert item["stock_name"] == "Fresh Trend"
    assert item["sector_name"] == "Electronics"
    assert item["concepts"] == ["Chiplet", "AI hardware"]
    assert item["return_20d"] >= 0.08
    assert item["return_60d"] >= 0.18
    assert item["return_120d"] >= 0.30
    assert item["score"] > 0


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
