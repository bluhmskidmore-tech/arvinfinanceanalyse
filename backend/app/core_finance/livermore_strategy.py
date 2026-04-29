from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

ConditionStatus = Literal["pass", "fail", "missing", "stale"]
MarketGateState = Literal["OFF", "WARM", "HOT", "OVERHEAT", "PENDING_DATA", "NO_DATA", "STALE"]


@dataclass(frozen=True)
class BroadIndexObservation:
    trade_date: date
    close: float
    quality_flag: str = "ok"
    source_series_id: str = "CA.CSI300"
    source_version: str = ""
    vendor_version: str = ""


def evaluate_market_gate(history: list[BroadIndexObservation]) -> dict[str, object]:
    ordered = sorted(history, key=lambda row: row.trade_date)
    conditions = [
        {
            "key": "csi300_close_gt_ma60",
            "label": "CSI300 close > MA60",
            "status": "missing",
            "evidence": "Broad-index history unavailable.",
            "source_series_id": "CA.CSI300",
        },
        {
            "key": "csi300_ma20_gt_ma60",
            "label": "CSI300 MA20 > MA60",
            "status": "missing",
            "evidence": "Broad-index history unavailable.",
            "source_series_id": "CA.CSI300",
        },
        {
            "key": "breadth_5d_positive",
            "label": "5-day breadth > 0",
            "status": "missing",
            "evidence": "Breadth inputs are not landed for the Phase 1 slice.",
            "source_series_id": None,
        },
        {
            "key": "limit_up_quality_positive",
            "label": "Limit-up seal/break quality positive",
            "status": "missing",
            "evidence": "Limit-up quality inputs are not landed for the Phase 1 slice.",
            "source_series_id": None,
        },
    ]
    if not ordered:
        return _build_gate(
            state="NO_DATA",
            exposure=0.0,
            passed_conditions=0,
            available_conditions=0,
            required_conditions=4,
            conditions=conditions,
        )

    latest = ordered[-1]
    if latest.quality_flag == "stale":
        for row in conditions[:2]:
            row["status"] = "stale"
            row["evidence"] = (
                f"Latest broad-index input {latest.trade_date.isoformat()} is marked stale."
            )
        return _build_gate(
            state="STALE",
            exposure=0.0,
            passed_conditions=0,
            available_conditions=2,
            required_conditions=4,
            conditions=conditions,
        )

    if len(ordered) < 60:
        evidence = f"Need at least 60 broad-index observations; found {len(ordered)}."
        conditions[0]["evidence"] = evidence
        conditions[1]["evidence"] = evidence
        return _build_gate(
            state="PENDING_DATA",
            exposure=0.0,
            passed_conditions=0,
            available_conditions=0,
            required_conditions=4,
            conditions=conditions,
        )

    closes = [row.close for row in ordered]
    ma20 = _moving_average(closes, 20)
    ma60 = _moving_average(closes, 60)
    close_gt_ma60 = closes[-1] > ma60
    ma20_gt_ma60 = ma20 > ma60
    conditions[0]["status"] = "pass" if close_gt_ma60 else "fail"
    conditions[0]["evidence"] = (
        f"Close {closes[-1]:.2f} vs MA60 {ma60:.2f} on {latest.trade_date.isoformat()}."
    )
    conditions[1]["status"] = "pass" if ma20_gt_ma60 else "fail"
    conditions[1]["evidence"] = (
        f"MA20 {ma20:.2f} vs MA60 {ma60:.2f} on {latest.trade_date.isoformat()}."
    )
    passed_conditions = int(close_gt_ma60) + int(ma20_gt_ma60)
    if passed_conditions == 0:
        state: MarketGateState = "OFF"
    else:
        # Phase 1 can only score the broad-index trend slice, so the hottest state
        # remains capped until breadth and limit-up inputs land.
        state = "WARM"
    return _build_gate(
        state=state,
        exposure=round(passed_conditions / 4, 4),
        passed_conditions=passed_conditions,
        available_conditions=2,
        required_conditions=4,
        conditions=conditions,
    )


def _moving_average(values: list[float], window: int) -> float:
    return sum(values[-window:]) / window


def _build_gate(
    *,
    state: MarketGateState,
    exposure: float,
    passed_conditions: int,
    available_conditions: int,
    required_conditions: int,
    conditions: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "state": state,
        "exposure": exposure,
        "passed_conditions": passed_conditions,
        "available_conditions": available_conditions,
        "required_conditions": required_conditions,
        "conditions": conditions,
    }
