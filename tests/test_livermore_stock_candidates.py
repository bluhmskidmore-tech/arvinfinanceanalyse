from __future__ import annotations

import math
from typing import Any, cast

import pytest

from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION,
    StockCandidateSnapshot,
    compute_stock_candidates,
)


def _close_history(*, start: float, step: float, count: int = 120) -> list[float]:
    return [round(start + step * index, 6) for index in range(count)]


def _turnover_history(*, baseline: float, current: float, count: int = 120) -> list[float]:
    return [baseline] * (count - 1) + [current]


def _ema(values: list[float], window: int) -> list[float]:
    alpha = 2.0 / (window + 1.0)
    ema: list[float] = []
    for value in values:
        if not ema:
            ema.append(value)
        else:
            ema.append(alpha * value + (1.0 - alpha) * ema[-1])
    return ema


def _snapshot(
    *,
    stock_code: str,
    stock_name: str,
    sector_code: str,
    sector_name: str,
    sector_rank: int,
    close_history: list[float],
    turnover_history: list[float],
    open_value: float,
    high_value: float,
    low_value: float,
    limit_ratio: float = 0.1,
    one_word_board: bool = False,
    closed_up_limit: bool = False,
) -> StockCandidateSnapshot:
    return StockCandidateSnapshot(
        stock_code=stock_code,
        stock_name=stock_name,
        sector_code=sector_code,
        sector_name=sector_name,
        sector_rank=sector_rank,
        open_value=open_value,
        high_value=high_value,
        low_value=low_value,
        close_value=close_history[-1],
        turnover_free=turnover_history[-1],
        limit_ratio=limit_ratio,
        one_word_board=one_word_board,
        closed_up_limit=closed_up_limit,
        close_history=close_history,
        turnover_history=turnover_history,
    )


def test_stock_candidates_emits_ranked_breakout_candidates_from_strategy_bundle_formula() -> None:
    alpha_closes = _close_history(start=10.0, step=0.1)
    beta_closes = _close_history(start=20.0, step=0.08)
    gamma_closes = _close_history(start=15.0, step=0.06)

    result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=[
            _snapshot(
                stock_code="000001.SZ",
                stock_name="Alpha",
                sector_code="801001",
                sector_name="AI",
                sector_rank=1,
                close_history=alpha_closes,
                turnover_history=_turnover_history(baseline=0.5, current=1.5),
                open_value=21.55,
                high_value=22.0,
                low_value=21.4,
            ),
            _snapshot(
                stock_code="000002.SZ",
                stock_name="Beta",
                sector_code="801002",
                sector_name="Bank",
                sector_rank=2,
                close_history=beta_closes,
                turnover_history=_turnover_history(baseline=0.4, current=1.25),
                open_value=29.38,
                high_value=29.62,
                low_value=29.2,
            ),
            _snapshot(
                stock_code="000003.SZ",
                stock_name="Gamma",
                sector_code="801004",
                sector_name="Retail",
                sector_rank=4,
                close_history=gamma_closes,
                turnover_history=_turnover_history(baseline=0.45, current=1.4),
                open_value=22.06,
                high_value=22.22,
                low_value=21.92,
            ),
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["as_of_date"] == "2026-04-29"
    assert payload["formula_version"] == FORMULA_VERSION
    assert payload["input_stock_count"] == 3
    assert payload["candidate_count"] == 2
    assert payload["excluded_stock_count"] == 1
    assert payload["insufficient_history_count"] == 0

    items = cast(list[dict[str, Any]], payload["items"])
    assert [row["stock_code"] for row in items] == ["000001.SZ", "000002.SZ"]
    assert [row["rank"] for row in items] == [1, 2]

    alpha = items[0]
    assert alpha["sector_rank"] == 1
    assert alpha["breakout_level"] == pytest.approx(max(alpha_closes[-56:-1]))
    assert alpha["close_strength"] == pytest.approx((21.9 - 21.4) / (22.0 - 21.4))
    assert alpha["gap_norm"] == pytest.approx(((21.55 - 21.8) / 21.8) / 0.1)
    assert alpha["abnormal_turnover"] == pytest.approx(math.log1p(1.5 / 0.5))
    assert alpha["ema10"] == pytest.approx(_ema(alpha_closes, 10)[-1])
    assert alpha["ma20"] > alpha["ma60"] > alpha["ma120"]


def test_stock_candidates_skip_market_off_and_count_insufficient_history() -> None:
    ready_snapshot = _snapshot(
        stock_code="000001.SZ",
        stock_name="Alpha",
        sector_code="801001",
        sector_name="AI",
        sector_rank=1,
        close_history=_close_history(start=10.0, step=0.1),
        turnover_history=_turnover_history(baseline=0.5, current=1.5),
        open_value=21.55,
        high_value=22.0,
        low_value=21.4,
    )
    short_history_snapshot = _snapshot(
        stock_code="000002.SZ",
        stock_name="Beta",
        sector_code="801002",
        sector_name="Bank",
        sector_rank=2,
        close_history=_close_history(start=10.0, step=0.1, count=60),
        turnover_history=_turnover_history(baseline=0.5, current=1.5, count=60),
        open_value=15.75,
        high_value=16.0,
        low_value=15.5,
    )

    warm_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=[ready_snapshot, short_history_snapshot],
    )
    assert warm_result.payload["candidate_count"] == 1
    assert warm_result.payload["excluded_stock_count"] == 1
    assert warm_result.payload["insufficient_history_count"] == 1

    off_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="OFF",
        snapshots=[ready_snapshot],
    )
    assert off_result.payload["candidate_count"] == 0
    assert off_result.payload["items"] == []


def test_stock_candidates_keep_only_top_six_ranked_breakouts_and_count_trimmed_tail() -> None:
    closes = _close_history(start=10.0, step=0.1)
    snapshots = [
        _snapshot(
            stock_code=f"00000{index}.SZ",
            stock_name=f"Stock {index}",
            sector_code="801001",
            sector_name="AI",
            sector_rank=1,
            close_history=closes,
            turnover_history=_turnover_history(baseline=0.5, current=current_turnover),
            open_value=21.55,
            high_value=22.0,
            low_value=21.6,
        )
        for index, current_turnover in enumerate([1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0], start=1)
    ]
    snapshots.append(
        _snapshot(
            stock_code="999999.SZ",
            stock_name="Excluded",
            sector_code="801009",
            sector_name="Other",
            sector_rank=4,
            close_history=closes,
            turnover_history=_turnover_history(baseline=0.5, current=1.5),
            open_value=21.55,
            high_value=22.0,
            low_value=21.6,
        )
    )

    result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=snapshots,
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["candidate_count"] == 6
    assert payload["excluded_stock_count"] == 3

    items = cast(list[dict[str, Any]], payload["items"])
    assert [row["stock_code"] for row in items] == [
        "000008.SZ",
        "000007.SZ",
        "000006.SZ",
        "000005.SZ",
        "000004.SZ",
        "000003.SZ",
    ]
    assert [row["rank"] for row in items] == [1, 2, 3, 4, 5, 6]
