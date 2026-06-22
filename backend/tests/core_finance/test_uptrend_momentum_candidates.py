from __future__ import annotations

from backend.app.core_finance.uptrend_momentum_candidates import (
    UptrendMomentumSnapshot,
    compute_uptrend_momentum_candidates,
)


def _snapshot(
    code: str,
    closes: list[float],
    *,
    name: str | None = None,
    sector_name: str = "Machinery",
    amount_ratio: float = 1.3,
    pctchange: float = 0.02,
) -> UptrendMomentumSnapshot:
    amount_history = [1000.0 for _ in closes]
    amount_history[-1] = 1000.0 * amount_ratio
    return UptrendMomentumSnapshot(
        stock_code=code,
        stock_name=name or code,
        sector_code="S1",
        sector_name=sector_name,
        close_value=closes[-1],
        pctchange=pctchange,
        turn=1.5,
        amplitude=3.0,
        close_history=closes,
        amount_history=amount_history,
    )


def test_uptrend_momentum_selects_stacked_ma_breakouts_without_chasing_extended_moves() -> None:
    steady_uptrend = [100.0 + i * 0.5 for i in range(121)]
    flat_stock = [100.0 for _ in range(121)]
    extended = [100.0 + i * 0.2 for i in range(120)] + [160.0]
    parabolic = [20.0 + i for i in range(121)]

    result = compute_uptrend_momentum_candidates(
        as_of_date="2026-06-18",
        market_state="HOT",
        snapshots=[
            _snapshot("000001.SZ", steady_uptrend, name="Trend A"),
            _snapshot("000002.SZ", flat_stock, name="Flat B"),
            _snapshot("000003.SZ", extended, name="Extended C"),
            _snapshot("000004.SZ", parabolic, name="Parabolic D"),
        ],
    )

    payload = result.payload
    assert payload["formula_version"] == "rv_uptrend_momentum_candidates_v1"
    assert payload["candidate_count"] == 1
    assert payload["excluded_stock_count"] == 3

    item = payload["items"][0]
    assert item["rank"] == 1
    assert item["stock_code"] == "000001.SZ"
    assert item["stock_name"] == "Trend A"
    assert item["close"] > item["ma20"] > item["ma60"] > item["ma120"]
    assert item["return_20d"] > 0
    assert item["return_60d"] > 0
    assert item["return_120d"] > 0
    assert 0 < item["close_to_ma20"] <= 0.20
    assert item["amount_ratio"] == 1.3
    assert item["score"] > 0


def test_uptrend_momentum_pauses_when_market_is_off() -> None:
    result = compute_uptrend_momentum_candidates(
        as_of_date="2026-06-18",
        market_state="OFF",
        snapshots=[_snapshot("000001.SZ", [100.0 + i for i in range(121)])],
    )

    assert result.payload["candidate_count"] == 0
    assert result.payload["input_stock_count"] == 1
    assert result.payload["excluded_stock_count"] == 1
