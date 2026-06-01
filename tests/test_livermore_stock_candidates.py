from __future__ import annotations

import math
from typing import Any, cast

import pytest

from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION,
    StockCandidateSnapshot,
    compute_stock_candidates,
)


class _CountingHistory(list[float]):
    iteration_count = 0

    def __iter__(self):  # type: ignore[override]
        type(self).iteration_count += 1
        return super().__iter__()


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
    pe: float | None = None,
    pb: float | None = None,
    ps: float | None = None,
    roe: float | None = None,
    gross_margin: float | None = None,
    three_month_return: float | None = None,
    twelve_month_return: float | None = None,
    volatility: float | None = None,
    dividend_yield: float | None = None,
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
        pe=pe,
        pb=pb,
        ps=ps,
        roe=roe,
        gross_margin=gross_margin,
        three_month_return=three_month_return,
        twelve_month_return=twelve_month_return,
        volatility=volatility,
        dividend_yield=dividend_yield,
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
                open_value=21.85,
                high_value=21.92,
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
                open_value=29.45,
                high_value=29.53,
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
    assert [row["stock_code"] for row in items] == ["000002.SZ", "000001.SZ"]
    assert [row["rank"] for row in items] == [1, 2]

    alpha = next(row for row in items if row["stock_code"] == "000001.SZ")
    assert alpha["sector_rank"] == 1
    assert alpha["breakout_level"] == pytest.approx(max(alpha_closes[-56:-1]))
    assert alpha["close_strength"] == pytest.approx((21.9 - 21.4) / (21.92 - 21.4))
    assert alpha["gap_norm"] == pytest.approx(((21.85 - 21.8) / 21.8) / 0.1, abs=1e-6)
    assert alpha["breakout_extension_norm"] == pytest.approx(((21.9 - 21.8) / 21.8) / 0.1, abs=1e-6)
    assert alpha["abnormal_turnover"] == pytest.approx(math.log1p(1.5 / 0.5))
    assert alpha["ema10"] == pytest.approx(_ema(alpha_closes, 10)[-1])
    assert alpha["ma20"] > alpha["ma60"] > alpha["ma120"]


def test_stock_candidates_do_not_rescan_history_when_excluding_non_signal_rows() -> None:
    _CountingHistory.iteration_count = 0
    closes = _CountingHistory(_close_history(start=10.0, step=0.1))
    turns = _CountingHistory(_turnover_history(baseline=0.5, current=1.5))

    result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=[
            _snapshot(
                stock_code="000003.SZ",
                stock_name="Gamma",
                sector_code="801004",
                sector_name="Retail",
                sector_rank=4,
                close_history=closes,
                turnover_history=turns,
                open_value=22.06,
                high_value=22.22,
                low_value=21.92,
            )
        ],
    )

    payload = cast(dict[str, Any], result.payload)
    assert payload["candidate_count"] == 0
    assert payload["insufficient_history_count"] == 0
    assert _CountingHistory.iteration_count == 2


def test_stock_candidates_skip_market_off_and_count_insufficient_history() -> None:
    ready_snapshot = _snapshot(
        stock_code="000001.SZ",
        stock_name="Alpha",
        sector_code="801001",
        sector_name="AI",
        sector_rank=1,
        close_history=_close_history(start=10.0, step=0.1),
        turnover_history=_turnover_history(baseline=0.5, current=1.5),
        open_value=21.85,
        high_value=21.92,
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
        open_value=15.81,
        high_value=15.97,
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
            open_value=21.85,
            high_value=21.91,
            low_value=21.6,
        )
        for index, current_turnover in enumerate([1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4], start=1)
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
            open_value=21.85,
            high_value=21.91,
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


def test_stock_candidates_apply_fundamental_overlay_when_factor_inputs_are_available() -> None:
    closes = _close_history(start=10.0, step=0.1)
    snapshots = [
        _snapshot(
            stock_code="000001.SZ",
            stock_name="Hot Weak Fundamentals",
            sector_code="801001",
            sector_name="AI",
            sector_rank=1,
            close_history=closes,
            turnover_history=_turnover_history(baseline=0.5, current=1.5),
            open_value=21.85,
            high_value=21.91,
            low_value=21.6,
            pe=180.0,
            pb=18.0,
            ps=28.0,
            roe=-0.08,
            gross_margin=-0.02,
            three_month_return=-0.20,
            twelve_month_return=-0.30,
            volatility=0.80,
            dividend_yield=0.0,
        ),
        _snapshot(
            stock_code="000002.SZ",
            stock_name="Quality One",
            sector_code="801001",
            sector_name="AI",
            sector_rank=1,
            close_history=closes,
            turnover_history=_turnover_history(baseline=0.5, current=1.8),
            open_value=21.85,
            high_value=21.91,
            low_value=21.6,
            pe=12.0,
            pb=1.5,
            ps=2.0,
            roe=0.18,
            gross_margin=0.35,
            three_month_return=0.12,
            twelve_month_return=0.20,
            volatility=0.22,
            dividend_yield=0.025,
        ),
        _snapshot(
            stock_code="000003.SZ",
            stock_name="Quality Two",
            sector_code="801002",
            sector_name="Power",
            sector_rank=2,
            close_history=closes,
            turnover_history=_turnover_history(baseline=0.5, current=1.6),
            open_value=21.85,
            high_value=21.91,
            low_value=21.6,
            pe=16.0,
            pb=1.2,
            ps=1.6,
            roe=0.14,
            gross_margin=0.30,
            three_month_return=0.08,
            twelve_month_return=0.18,
            volatility=0.18,
            dividend_yield=0.035,
        ),
        _snapshot(
            stock_code="000004.SZ",
            stock_name="Crowded Weak Fundamentals",
            sector_code="801003",
            sector_name="Retail",
            sector_rank=3,
            close_history=closes,
            turnover_history=_turnover_history(baseline=0.5, current=1.8),
            open_value=21.85,
            high_value=21.91,
            low_value=21.6,
            pe=120.0,
            pb=12.0,
            ps=18.0,
            roe=0.01,
            gross_margin=0.03,
            three_month_return=-0.05,
            twelve_month_return=-0.10,
            volatility=0.65,
            dividend_yield=0.0,
        ),
    ]

    result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="HOT",
        snapshots=snapshots,
    )

    payload = cast(dict[str, Any], result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    assert payload["candidate_count"] == 2
    assert payload["fundamental_overlay"] == {
        "status": "applied",
        "input_candidate_count": 4,
        "valid_factor_count": 4,
        "selected_factor_count": 2,
        "top_fraction": 0.5,
    }
    assert [row["stock_code"] for row in items] == ["000002.SZ", "000003.SZ"]
    assert all(row["factor_score"] is not None for row in items)
    assert float(items[0]["abnormal_turnover"]) > float(items[1]["abnormal_turnover"])


def test_stock_candidates_can_emit_pre_truncation_universe_for_research() -> None:
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
            open_value=21.85,
            high_value=21.91,
            low_value=21.6,
        )
        for index, current_turnover in enumerate([1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4], start=1)
    ]

    default_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=snapshots,
    )
    assert "universe_items" not in default_result.payload

    research_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=snapshots,
        include_universe=True,
    )

    payload = cast(dict[str, Any], research_result.payload)
    items = cast(list[dict[str, Any]], payload["items"])
    universe = cast(list[dict[str, Any]], payload["universe_items"])
    assert len(items) == 6
    assert len(universe) == 7
    assert [row["new_rank"] for row in universe] == list(range(1, 8))
    assert [row["eligible_before_truncation"] for row in universe] == [True] * 7
    assert [row["selected_new_top6"] for row in universe] == [True] * 6 + [False]
    assert [row["stock_code"] for row in universe[:6]] == [row["stock_code"] for row in items]


def test_stock_candidates_exclude_overextended_breakouts_after_pivot_only_when_market_overheats() -> None:
    controlled_closes = _close_history(start=10.0, step=0.1)
    overextended_closes = [*controlled_closes[:-1], 22.7]
    controlled_snapshot = _snapshot(
        stock_code="000001.SZ",
        stock_name="Controlled",
        sector_code="801001",
        sector_name="AI",
        sector_rank=1,
        close_history=controlled_closes,
        turnover_history=_turnover_history(baseline=0.5, current=1.5),
        open_value=21.85,
        high_value=21.92,
        low_value=21.4,
    )
    overextended_snapshot = _snapshot(
        stock_code="000002.SZ",
        stock_name="Extended",
        sector_code="801001",
        sector_name="AI",
        sector_rank=1,
        close_history=overextended_closes,
        turnover_history=_turnover_history(baseline=0.5, current=1.5),
        open_value=22.65,
        high_value=22.72,
        low_value=22.1,
    )

    warm_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=[controlled_snapshot, overextended_snapshot],
    )

    warm_payload = cast(dict[str, Any], warm_result.payload)
    assert warm_payload["candidate_count"] == 2
    warm_items = cast(list[dict[str, Any]], warm_payload["items"])
    assert {row["stock_code"] for row in warm_items} == {"000001.SZ", "000002.SZ"}

    overheat_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="OVERHEAT",
        snapshots=[controlled_snapshot, overextended_snapshot],
    )

    overheat_payload = cast(dict[str, Any], overheat_result.payload)
    assert overheat_payload["candidate_count"] == 1
    assert overheat_payload["excluded_stock_count"] == 1
    overheat_items = cast(list[dict[str, Any]], overheat_payload["items"])
    assert overheat_items[0]["stock_code"] == "000001.SZ"
    assert overheat_items[0]["breakout_extension_norm"] <= 0.35


def test_stock_candidates_exp3b_policy_keeps_entry_only_stricter_gate_and_sorts_by_close_strength_first() -> None:
    closes = _close_history(start=10.0, step=0.1)
    higher_turn_lower_close_strength = _snapshot(
        stock_code="000001.SZ",
        stock_name="Turnover First",
        sector_code="801001",
        sector_name="AI",
        sector_rank=1,
        close_history=closes,
        turnover_history=_turnover_history(baseline=0.5, current=3.0),
        open_value=22.05,
        high_value=21.91,
        low_value=20.65,
    )
    higher_close_strength_lower_turn = _snapshot(
        stock_code="000002.SZ",
        stock_name="Close Strength First",
        sector_code="801002",
        sector_name="Bank",
        sector_rank=2,
        close_history=closes,
        turnover_history=_turnover_history(baseline=0.5, current=2.5),
        open_value=22.0,
        high_value=21.905,
        low_value=20.65,
    )
    weak_close_strength = _snapshot(
        stock_code="000003.SZ",
        stock_name="Weak Close",
        sector_code="801003",
        sector_name="Power",
        sector_rank=3,
        close_history=closes,
        turnover_history=_turnover_history(baseline=0.5, current=2.5),
        open_value=22.0,
        high_value=22.05,
        low_value=21.0,
    )
    too_wide_gap = _snapshot(
        stock_code="000004.SZ",
        stock_name="Wide Gap",
        sector_code="801004",
        sector_name="Retail",
        sector_rank=2,
        close_history=closes,
        turnover_history=_turnover_history(baseline=0.5, current=2.5),
        open_value=22.7,
        high_value=21.905,
        low_value=20.65,
    )
    too_hot_turnover = _snapshot(
        stock_code="000005.SZ",
        stock_name="Hot Turnover",
        sector_code="801005",
        sector_name="Auto",
        sector_rank=2,
        close_history=closes,
        turnover_history=_turnover_history(baseline=0.5, current=5.5),
        open_value=22.0,
        high_value=21.905,
        low_value=20.65,
    )

    default_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=[higher_turn_lower_close_strength, higher_close_strength_lower_turn],
    )
    default_items = cast(list[dict[str, Any]], cast(dict[str, Any], default_result.payload)["items"])
    assert [row["stock_code"] for row in default_items] == ["000001.SZ", "000002.SZ"]

    exp3b_result = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="WARM",
        snapshots=[
            higher_turn_lower_close_strength,
            higher_close_strength_lower_turn,
            weak_close_strength,
            too_wide_gap,
            too_hot_turnover,
        ],
        policy_name="exp3b",
    )
    exp3b_payload = cast(dict[str, Any], exp3b_result.payload)
    exp3b_items = cast(list[dict[str, Any]], exp3b_payload["items"])
    assert exp3b_payload["selection_policy"] == "exp3b"
    assert [row["stock_code"] for row in exp3b_items] == ["000002.SZ", "000001.SZ"]
    assert [row["rank"] for row in exp3b_items] == [1, 2]
    assert all(float(row["close_strength"]) >= 0.99 for row in exp3b_items)
    assert all(float(row["gap_norm"]) <= 0.35 for row in exp3b_items)
    assert all(1.2 <= float(row["abnormal_turnover"]) <= 2.4 for row in exp3b_items)

    exp3b_overheat = compute_stock_candidates(
        as_of_date="2026-04-29",
        market_state="OVERHEAT",
        snapshots=[higher_turn_lower_close_strength, higher_close_strength_lower_turn],
        policy_name="exp3b",
    )
    assert exp3b_overheat.payload["selection_policy"] == "exp3b"
    assert exp3b_overheat.payload["candidate_count"] == 0
    assert exp3b_overheat.payload["items"] == []
