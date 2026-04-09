from __future__ import annotations

from pydantic import BaseModel


class ExecutiveMetric(BaseModel):
    id: str
    label: str
    value: str
    delta: str
    tone: str
    detail: str


class OverviewPayload(BaseModel):
    title: str
    metrics: list[ExecutiveMetric]


class SummaryPoint(BaseModel):
    id: str
    label: str
    tone: str
    text: str


class SummaryPayload(BaseModel):
    title: str
    narrative: str
    points: list[SummaryPoint]


class AttributionSegment(BaseModel):
    id: str
    label: str
    amount: float
    display_amount: str
    tone: str


class PnlAttributionPayload(BaseModel):
    title: str
    total: str
    segments: list[AttributionSegment]


class RiskSignal(BaseModel):
    id: str
    label: str
    value: str
    status: str
    detail: str


class RiskOverviewPayload(BaseModel):
    title: str
    signals: list[RiskSignal]


class ContributionRow(BaseModel):
    id: str
    name: str
    owner: str
    contribution: str
    completion: int
    status: str


class ContributionPayload(BaseModel):
    title: str
    rows: list[ContributionRow]


class AlertItem(BaseModel):
    id: str
    severity: str
    title: str
    occurred_at: str
    detail: str


class AlertsPayload(BaseModel):
    title: str
    items: list[AlertItem]
