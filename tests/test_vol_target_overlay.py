from __future__ import annotations

import pytest

from backend.app.core_finance.vol_target_overlay import (
    build_vol_target_index_comparison,
    calculate_vol_target_multipliers,
)


def _return_rows(values: list[float]) -> list[dict[str, object]]:
    return [
        {"date": f"2026-01-{index + 1:02d}", "daily_return": value}
        for index, value in enumerate(values)
    ]


def test_vol_target_multiplier_cuts_high_vol_window() -> None:
    rows = _return_rows([0.05 if index % 2 == 0 else -0.05 for index in range(21)])

    points = calculate_vol_target_multipliers(rows, target_vol=0.15, window=20)

    assert points[-1]["insufficient_history"] is False
    assert points[-1]["realized_vol"] > 0.15
    assert points[-1]["multiplier"] < 1.0


def test_vol_target_multiplier_stays_one_for_low_vol_window() -> None:
    rows = _return_rows([0.001 for _ in range(21)])

    points = calculate_vol_target_multipliers(rows, target_vol=0.15, window=20)

    assert points[-1]["insufficient_history"] is False
    assert points[-1]["multiplier"] == pytest.approx(1.0)


def test_vol_target_multiplier_uses_no_future_returns() -> None:
    first_twenty = [0.02 if index % 2 == 0 else -0.02 for index in range(20)]
    calm_future = _return_rows([*first_twenty, 0.001, 0.001, 0.001])
    wild_future = _return_rows([*first_twenty, 0.20, -0.20, 0.20])

    calm_points = calculate_vol_target_multipliers(calm_future, target_vol=0.15, window=20)
    wild_points = calculate_vol_target_multipliers(wild_future, target_vol=0.15, window=20)

    assert calm_points[19]["multiplier"] == pytest.approx(wild_points[19]["multiplier"])
    assert calm_points[19]["realized_vol"] == pytest.approx(wild_points[19]["realized_vol"])


def test_vol_target_multiplier_ignores_same_day_return() -> None:
    rows_a = _return_rows([0.01, -0.02, 0.015, -0.01, 0.001, 0.001])
    rows_b = _return_rows([0.01, -0.02, 0.015, -0.01, 0.25, 0.001])

    points_a = calculate_vol_target_multipliers(rows_a, target_vol=0.15, window=3)
    points_b = calculate_vol_target_multipliers(rows_b, target_vol=0.15, window=3)

    assert points_a[4]["multiplier"] == pytest.approx(points_b[4]["multiplier"])
    assert points_a[4]["realized_vol"] == pytest.approx(points_b[4]["realized_vol"])


def test_vol_target_exposure_is_t_plus_1_effective() -> None:
    base_returns = [0.01, -0.02, 0.015, -0.01, 0.001, 0.001]
    shocked_returns = [0.01, -0.02, 0.015, -0.01, 0.25, 0.001]
    base_rows = _return_rows(base_returns)
    shocked_rows = _return_rows(shocked_returns)
    exposure_rows = [{"date": row["date"], "exposure": 1.0} for row in base_rows]

    base_payload = build_vol_target_index_comparison(
        base_rows,
        exposure_rows=exposure_rows,
        exposure_by_market_state={"OFF": (0.0,)},
        target_vol=0.15,
        window=3,
        initial_capital=100.0,
    )
    shocked_payload = build_vol_target_index_comparison(
        shocked_rows,
        exposure_rows=exposure_rows,
        exposure_by_market_state={"OFF": (0.0,)},
        target_vol=0.15,
        window=3,
        initial_capital=100.0,
    )

    t_date = base_rows[4]["date"]
    t_plus_1_date = base_rows[5]["date"]
    base_exposure = base_payload["vol_target_exposure_by_date"]
    shocked_exposure = shocked_payload["vol_target_exposure_by_date"]

    assert base_exposure[t_date] == pytest.approx(shocked_exposure[t_date])
    assert base_exposure[t_plus_1_date] != pytest.approx(shocked_exposure[t_plus_1_date])


def test_vol_target_index_comparison_reports_avg_exposure_and_multiplier() -> None:
    benchmark_rows = [
        {"date": f"2026-01-{index + 1:02d}", "daily_return": 0.05 if index % 2 == 0 else -0.05}
        for index in range(22)
    ]
    exposure_rows = [
        {"date": row["date"], "exposure": 1.0}
        for row in benchmark_rows
    ]

    payload = build_vol_target_index_comparison(
        benchmark_rows,
        exposure_rows=exposure_rows,
        exposure_by_market_state={"OFF": (0.0,)},
        target_vol=0.15,
        window=20,
        initial_capital=100.0,
    )

    assert payload["status"] == "ready"
    metrics = payload["metrics"]
    assert metrics["gate_index"]["avg_exposure"] == pytest.approx(1.0)
    assert metrics["gate_voltarget_index"]["avg_exposure"] < 1.0
    assert metrics["gate_voltarget_index"]["avg_multiplier"] < 1.0
    assert metrics["gate_voltarget_index"]["insufficient_history_days"] == 20


def test_gate_exposure_applies_with_one_day_lag() -> None:
    """T 日收盘决定的 gate 敞口只能吃 T+1 日收益（2026-07-19 审计 宏观 H-1）。

    第 3 日敞口从 1.0 切到 0.0：第 3 日收益仍按前一日敞口 1.0 结算，
    第 4 日收益才按 0.0 结算。
    """
    returns = [0.0, 0.10, 0.10, 0.10]
    rows = _return_rows(returns)
    exposure_rows = [
        {"date": rows[0]["date"], "exposure": 1.0},
        {"date": rows[1]["date"], "exposure": 1.0},
        {"date": rows[2]["date"], "exposure": 0.0},
        {"date": rows[3]["date"], "exposure": 0.0},
    ]

    payload = build_vol_target_index_comparison(
        rows,
        exposure_rows=exposure_rows,
        exposure_by_market_state={"OFF": (0.0,)},
        target_vol=0.15,
        window=3,
        initial_capital=100.0,
    )

    curves = payload["curves"]
    # 第 2 日（敞口 1.0，前日决策 1.0）吃到 10%
    assert curves[1]["gate_index"] == pytest.approx(110.0)
    # 第 3 日：当日决策已切 0，但收益仍按前一日（1.0）结算 -> 继续涨 10%
    assert curves[2]["gate_exposure"] == pytest.approx(1.0)
    assert curves[2]["gate_index"] == pytest.approx(121.0)
    # 第 4 日：前一日决策 0.0 生效 -> 不再吃收益
    assert curves[3]["gate_exposure"] == pytest.approx(0.0)
    assert curves[3]["gate_index"] == pytest.approx(121.0)


def test_vol_target_index_comparison_blocks_without_benchmark_rows() -> None:
    payload = build_vol_target_index_comparison(
        [],
        exposure_rows=[{"date": "2026-01-01", "exposure": 1.0}],
        exposure_by_market_state={"OFF": (0.0,)},
        target_vol=0.15,
        window=20,
        initial_capital=100.0,
    )

    assert payload == {
        "status": "benchmark_unavailable",
        "target_vol": 0.15,
        "window": 20,
        "curves": [],
        "metrics": {},
    }
