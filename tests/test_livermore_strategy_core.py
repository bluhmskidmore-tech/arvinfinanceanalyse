from __future__ import annotations

from datetime import date, timedelta

from backend.app.core_finance.livermore_strategy import (
    BroadIndexObservation,
    MarketGateSupplement,
    evaluate_market_gate,
)

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]



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


def test_market_gate_pending_when_supplement_inputs_are_missing() -> None:
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


def test_market_gate_overheat_when_supplement_covers_breadth_and_limit_up() -> None:
    start = date(2026, 1, 1)
    closes = [3000.0 + day * 10 for day in range(65)]
    history = _history(start=start, closes=closes)
    latest = history[-1].trade_date
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=latest,
            breadth_5d=12.3,
            limit_up_quality_ok=True,
        ),
    )
    assert gate["state"] == "OVERHEAT"
    assert gate["passed_conditions"] == 4
    assert gate["available_conditions"] == 4
    assert gate["exposure"] == 1.0
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["breadth_5d_positive"]["status"] == "pass"
    assert condition_by_key["limit_up_quality_positive"]["status"] == "pass"


def test_market_gate_exposure_scales_when_one_of_four_conditions_fails() -> None:
    start = date(2026, 1, 1)
    closes = [3000.0 + day * 10 for day in range(65)]
    history = _history(start=start, closes=closes)
    latest = history[-1].trade_date
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=latest,
            breadth_5d=42.0,
            limit_up_quality_ok=False,
        ),
    )
    assert gate["state"] == "HOT"
    assert gate["passed_conditions"] == 3
    assert gate["available_conditions"] == 4
    assert gate["exposure"] == 0.75
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["breadth_5d_positive"]["status"] == "pass"
    assert condition_by_key["limit_up_quality_positive"]["status"] == "fail"


def test_market_gate_negative_breadth_fails_condition() -> None:
    start = date(2026, 1, 1)
    closes = [3000.0 + day * 10 for day in range(65)]
    history = _history(start=start, closes=closes)
    latest = history[-1].trade_date
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=latest,
            breadth_5d=-120.0,
            limit_up_quality_ok=True,
        ),
    )
    assert gate["state"] == "HOT"
    assert gate["passed_conditions"] == 3
    assert gate["available_conditions"] == 4
    assert gate["exposure"] == 0.75
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["breadth_5d_positive"]["status"] == "fail"


def test_market_gate_partial_supplement_keeps_missing_leg_degraded() -> None:
    """Only breadth landed: exposure denominator stays 4 and state stays capped at WARM."""
    start = date(2026, 1, 1)
    closes = [3000.0 + day * 10 for day in range(65)]
    history = _history(start=start, closes=closes)
    latest = history[-1].trade_date
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=latest,
            breadth_5d=42.0,
            limit_up_quality_ok=None,
        ),
    )
    assert gate["state"] == "WARM"
    assert gate["passed_conditions"] == 3
    assert gate["available_conditions"] == 3
    assert gate["required_conditions"] == 4
    assert gate["exposure"] == 0.75
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["breadth_5d_positive"]["status"] == "pass"
    assert condition_by_key["limit_up_quality_positive"]["status"] == "missing"


def test_market_gate_pending_when_supplement_trade_date_mismatches() -> None:
    start = date(2026, 1, 1)
    closes = [3000.0 + day * 10 for day in range(65)]
    history = _history(start=start, closes=closes)
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=date(2020, 1, 1),
            breadth_5d=12.3,
            limit_up_quality_ok=True,
        ),
    )
    assert gate["state"] == "WARM"
    assert gate["passed_conditions"] == 2
    assert gate["available_conditions"] == 2
    assert gate["exposure"] == 0.5
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["csi300_close_gt_ma60"]["status"] == "pass"
    assert condition_by_key["csi300_ma20_gt_ma60"]["status"] == "pass"
    assert condition_by_key["breadth_5d_positive"]["status"] == "missing"
    assert condition_by_key["limit_up_quality_positive"]["status"] == "missing"
