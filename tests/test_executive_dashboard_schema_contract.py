"""Contract tests for `backend.app.schemas.executive_dashboard` Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.common_numeric import Numeric
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


def _assert_numeric_json_shape(x: object) -> None:
    assert isinstance(x, dict)
    assert set(x.keys()) == {"raw", "unit", "display", "precision", "sign_aware"}
    assert isinstance(x["display"], str) and x["display"]


def test_overview_payload_round_trip() -> None:
    payload = OverviewPayload(
        title="t",
        metrics=[
            ExecutiveMetric(
                id="m1",
                label="L",
                value=Numeric(raw=1.0, unit="yuan", display="1", precision=0, sign_aware=False),
                delta=Numeric(raw=None, unit="pct", display="+", precision=0, sign_aware=True),
                tone="n",
                detail="d",
            )
        ],
    )
    d = payload.model_dump(mode="json")
    assert d["title"] == "t"
    assert len(d["metrics"]) == 1
    assert d["metrics"][0]["id"] == "m1"
    v = d["metrics"][0]["value"]
    _assert_numeric_json_shape(v)
    assert v["display"] == "1"


def test_summary_payload_round_trip() -> None:
    payload = SummaryPayload(
        title="s",
        report_date="2026-02-28",
        narrative="n",
        points=[SummaryPoint(id="p1", label="x", tone="t", text="body")],
    )
    d = payload.model_dump()
    assert d["report_date"] == "2026-02-28"
    assert d["narrative"] == "n"
    assert d["points"][0]["text"] == "body"


def test_pnl_attribution_payload_round_trip() -> None:
    payload = PnlAttributionPayload(
        title="a",
        total=Numeric(raw=100.0, unit="yuan", display="100", precision=0, sign_aware=True),
        segments=[
            AttributionSegment(
                id="seg",
                label="L",
                amount=Numeric(
                    raw=12.5 * 1e8,
                    unit="yuan",
                    display="12.50",
                    precision=2,
                    sign_aware=True,
                ),
                tone="ok",
            )
        ],
    )
    d = payload.model_dump(mode="json")
    _assert_numeric_json_shape(d["total"])
    assert d["total"]["display"] == "100"
    amt = d["segments"][0]["amount"]
    _assert_numeric_json_shape(amt)
    assert isinstance(amt["raw"], float)
    assert amt["raw"] == pytest.approx(12.5 * 1e8)


def test_risk_overview_payload_round_trip() -> None:
    payload = RiskOverviewPayload(
        title="r",
        signals=[RiskSignal(id="r1", label="R", value="v", status="ok", detail="d")],
    )
    d = payload.model_dump(mode="json")
    assert d["signals"][0]["status"] == "ok"
    val = d["signals"][0]["value"]
    _assert_numeric_json_shape(val)
    assert val["display"] == "v"


def test_contribution_payload_round_trip() -> None:
    payload = ContributionPayload(
        title="c",
        rows=[
            ContributionRow(
                id="row1",
                name="N",
                owner="O",
                contribution=Numeric(
                    raw=None,
                    unit="yuan",
                    display="10%",
                    precision=0,
                    sign_aware=True,
                ),
                completion=50,
                status="open",
            )
        ],
    )
    d = payload.model_dump(mode="json")
    assert d["rows"][0]["completion"] == 50
    assert isinstance(d["rows"][0]["completion"], int)
    c = d["rows"][0]["contribution"]
    _assert_numeric_json_shape(c)
    assert c["display"] == "10%"


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
