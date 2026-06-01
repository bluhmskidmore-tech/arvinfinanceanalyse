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


@dataclass(frozen=True)
class MarketGateSupplement:
    """Optional per-day inputs for breadth and limit-up gate legs (DuckDB analytical slice)."""

    trade_date: date
    breadth_5d: float | None = None
    limit_up_quality_ok: bool | None = None


def evaluate_market_gate(
    history: list[BroadIndexObservation],
    supplement: MarketGateSupplement | None = None,
) -> dict[str, object]:
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
    trend_passed = int(close_gt_ma60) + int(ma20_gt_ma60)

    sup_ok = bool(
        supplement is not None
        and supplement.trade_date == latest.trade_date
    )
    breadth_avail = bool(sup_ok and supplement is not None and supplement.breadth_5d is not None)
    lim_avail = bool(sup_ok and supplement is not None and supplement.limit_up_quality_ok is not None)

    breadth_passed = 0
    if breadth_avail and supplement is not None:
        b = supplement.breadth_5d
        if b is not None:
            conditions[2]["status"] = "pass" if b > 0 else "fail"
            conditions[2]["evidence"] = (
                f"5-day breadth {b:.4f} on {latest.trade_date.isoformat()} "
                f"(fact_livermore_gate_supplement_daily)."
            )
            breadth_passed = int(b > 0)

    lim_passed = 0
    if lim_avail and supplement is not None:
        ok = supplement.limit_up_quality_ok
        if ok is not None:
            conditions[3]["status"] = "pass" if ok else "fail"
            conditions[3]["evidence"] = (
                f"Limit-up quality {'positive' if ok else 'not positive'} on "
                f"{latest.trade_date.isoformat()} (fact_livermore_gate_supplement_daily)."
            )
            lim_passed = int(bool(ok))

    passed_conditions = trend_passed + breadth_passed + lim_passed
    available_conditions = 2 + int(breadth_avail) + int(lim_avail)

    state = _gate_state_from_passes(
        passed_conditions=passed_conditions,
        available_conditions=available_conditions,
        trend_passed=trend_passed,
    )
    return _build_gate(
        state=state,
        exposure=round(passed_conditions / 4, 4),
        passed_conditions=passed_conditions,
        available_conditions=available_conditions,
        required_conditions=4,
        conditions=conditions,
    )


def _gate_state_from_passes(
    *,
    passed_conditions: int,
    available_conditions: int,
    trend_passed: int,
) -> MarketGateState:
    if passed_conditions == 0:
        return "OFF"
    if available_conditions < 4:
        return "OFF" if trend_passed == 0 else "WARM"
    if passed_conditions == 4:
        return "OVERHEAT"
    if passed_conditions >= 3:
        return "HOT"
    return "WARM"


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
