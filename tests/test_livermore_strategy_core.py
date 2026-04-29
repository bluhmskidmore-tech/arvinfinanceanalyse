from __future__ import annotations

from datetime import date, timedelta

from backend.app.core_finance.livermore_strategy import BroadIndexObservation, evaluate_market_gate


def _history(*, start: date, closes: list[float], quality_flag: str = "ok") -> list[BroadIndexObservation]:
    return [
        BroadIndexObservation(
            trade_date=start + timedelta(days=offset),
            close=close,
            quality_flag=quality_flag,
            source_series_id="CA.CSI300",
        )
        for offset, close in enumerate(closes)
    ]


def test_market_gate_pending_when_fewer_than_60_points() -> None:
    gate = evaluate_market_gate(
        _history(
            start=date(2026, 1, 1),
            closes=[3500.0 + day for day in range(59)],
        )
    )

    assert gate["state"] == "PENDING_DATA"
    assert gate["passed_conditions"] == 0
    assert gate["available_conditions"] == 0
    assert gate["required_conditions"] == 4
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["csi300_close_gt_ma60"]["status"] == "missing"
    assert condition_by_key["csi300_ma20_gt_ma60"]["status"] == "missing"
    assert condition_by_key["breadth_5d_positive"]["status"] == "missing"
    assert condition_by_key["limit_up_quality_positive"]["status"] == "missing"


def test_market_gate_warm_when_two_trend_conditions_pass() -> None:
    gate = evaluate_market_gate(
        _history(
            start=date(2026, 1, 1),
            closes=[3000.0 + day * 10 for day in range(65)],
        )
    )

    assert gate["state"] == "WARM"
    assert gate["passed_conditions"] == 2
    assert gate["available_conditions"] == 2
    assert gate["required_conditions"] == 4
    assert gate["exposure"] == 0.5
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["csi300_close_gt_ma60"]["status"] == "pass"
    assert condition_by_key["csi300_ma20_gt_ma60"]["status"] == "pass"
    assert condition_by_key["breadth_5d_positive"]["status"] == "missing"
    assert condition_by_key["limit_up_quality_positive"]["status"] == "missing"
