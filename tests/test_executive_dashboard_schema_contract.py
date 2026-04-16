"""Contract tests for `backend.app.schemas.executive_dashboard` Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.executive_dashboard import (
    AlertItem,
    AlertsPayload,
    AttributionSegment,
    ContributionPayload,
    ContributionRow,
    ExecutiveMetric,
    OverviewPayload,
    PnlAttributionPayload,
    RiskOverviewPayload,
    RiskSignal,
    SummaryPayload,
    SummaryPoint,
)


def test_overview_payload_round_trip() -> None:
    payload = OverviewPayload(
        title="t",
        metrics=[ExecutiveMetric(id="m1", label="L", value="1", delta="+", tone="n", detail="d")],
    )
    d = payload.model_dump()
    assert d["title"] == "t"
    assert len(d["metrics"]) == 1
    assert d["metrics"][0]["id"] == "m1"
    assert d["metrics"][0]["value"] == "1"


def test_summary_payload_round_trip() -> None:
    payload = SummaryPayload(
        title="s",
        narrative="n",
        points=[SummaryPoint(id="p1", label="x", tone="t", text="body")],
    )
    d = payload.model_dump()
    assert d["narrative"] == "n"
    assert d["points"][0]["text"] == "body"


def test_pnl_attribution_payload_round_trip() -> None:
    payload = PnlAttributionPayload(
        title="a",
        total="100",
        segments=[
            AttributionSegment(
                id="seg",
                label="L",
                amount=12.5,
                display_amount="12.50",
                tone="ok",
            )
        ],
    )
    d = payload.model_dump()
    assert d["total"] == "100"
    assert d["segments"][0]["amount"] == 12.5
    assert isinstance(d["segments"][0]["amount"], float)


def test_risk_overview_payload_round_trip() -> None:
    payload = RiskOverviewPayload(
        title="r",
        signals=[RiskSignal(id="r1", label="R", value="v", status="ok", detail="d")],
    )
    d = payload.model_dump()
    assert d["signals"][0]["status"] == "ok"


def test_contribution_payload_round_trip() -> None:
    payload = ContributionPayload(
        title="c",
        rows=[
            ContributionRow(
                id="row1",
                name="N",
                owner="O",
                contribution="10%",
                completion=50,
                status="open",
            )
        ],
    )
    d = payload.model_dump()
    assert d["rows"][0]["completion"] == 50
    assert isinstance(d["rows"][0]["completion"], int)


def test_alerts_payload_round_trip() -> None:
    payload = AlertsPayload(
        title="al",
        items=[
            AlertItem(
                id="a1",
                severity="high",
                title="T",
                occurred_at="2026-01-01",
                detail="d",
            )
        ],
    )
    d = payload.model_dump()
    assert d["items"][0]["severity"] == "high"


@pytest.mark.parametrize(
    "model_cls,kwargs",
    [
        (ExecutiveMetric, {"label": "l", "value": "v", "delta": "d", "tone": "t", "detail": "x"}),
        (OverviewPayload, {"metrics": []}),
        (SummaryPoint, {"id": "i", "tone": "t", "text": "x"}),
        (SummaryPayload, {"narrative": "n", "points": []}),
        (AttributionSegment, {"id": "i", "label": "l", "display_amount": "0", "tone": "t"}),
        (PnlAttributionPayload, {"total": "0", "segments": []}),
            (RiskSignal, {"id": "i", "label": "l", "status": "s", "detail": "d"}),
        (RiskOverviewPayload, {"signals": []}),
        (ContributionRow, {"id": "i", "name": "n", "owner": "o", "contribution": "c", "status": "s"}),
        (ContributionPayload, {"rows": []}),
            (AlertItem, {"id": "i", "severity": "s", "occurred_at": "o", "detail": "d"}),
        (AlertsPayload, {"items": []}),
    ],
)
def test_required_fields_missing_raise(model_cls, kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        model_cls(**kwargs)
