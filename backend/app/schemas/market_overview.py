from __future__ import annotations

from typing import Any, Literal

from backend.app.schemas.macro_vendor import ChoiceMacroLatestPayload
from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, Field, model_validator

MarketOverviewPartitionStatus = Literal["ok", "degraded", "unavailable"]


class _StrictMarketOverviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarketOverviewConclusion(BaseModel):
    model_config = ConfigDict(extra="allow")

    stance: str | None = None
    tone: str | None = None
    summary: str | None = None
    recommended_action: str | None = None


class MarketOverviewComponent(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    quality_flag: str | None
    vendor_status: str | None
    basis: str | None
    cache_key: str | None
    fallback_mode: Literal["none", "latest_snapshot"] | None
    fallback_date: str | None
    formal_use_allowed: bool | None


class MarketOverviewGateEvidence(_StrictMarketOverviewModel):
    receipt_status: str | None = None
    receipt_generated_at: str | None = None
    receipt_age_hours: float | None = None
    missing_field_count: int | None = None


class MarketOverviewGateIssue(_StrictMarketOverviewModel):
    key: str
    label: str
    reason: str
    impact: str
    route: str


class MarketOverviewGate(_StrictMarketOverviewModel):
    level: Literal["ok", "review", "blocked"]
    reason_code: str
    human_reason: str
    recovery_action: str
    conclusion: MarketOverviewConclusion
    evidence: MarketOverviewGateEvidence
    issues: list[MarketOverviewGateIssue] = Field(default_factory=list)


class MarketOverviewDateSurface(_StrictMarketOverviewModel):
    key: str
    source: str
    status: MarketOverviewPartitionStatus
    reason: str | None
    latest: str | None
    age_days: int | None
    basis: str


class MarketOverviewTapeSpan(_StrictMarketOverviewModel):
    earliest: str | None
    latest: str | None


class MarketOverviewDates(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    surfaces: list[MarketOverviewDateSurface]
    tape_span: MarketOverviewTapeSpan
    computed_on: str
    date_basis: Literal["calendar_day"]


class MarketOverviewTapeSlot(_StrictMarketOverviewModel):
    key: str
    label: str
    kind: str
    status: Literal["ok", "degraded", "unavailable", "unresolved"]
    reason: str | None
    value: float | None
    unit: str | None
    change: float | None
    change_unit: str | None
    trade_date: str | None
    series_id: str | None
    series_name: str | None
    vendor: str | None
    basis: str | None
    fallback_mode: Literal["none", "latest_snapshot"] | None
    fallback_date: str | None
    formal_use_allowed: bool | None
    quality_flag: str
    tone_hint: str


class MarketOverviewTape(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    slots: list[MarketOverviewTapeSlot]


class MarketOverviewPulseItem(_StrictMarketOverviewModel):
    key: str
    label: str
    status: MarketOverviewPartitionStatus
    reason: str | None
    previous_value: float | None
    latest_value: float | None
    change: float | None
    change_kind: str
    unit: str | None
    change_unit: str | None
    latest_date: str | None
    source: str | None


class MarketOverviewPulse(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    items: list[MarketOverviewPulseItem]


class MarketOverviewCrisisDelta(_StrictMarketOverviewModel):
    window_points: int
    score_delta: float | None
    percentile_delta: float | None


class MarketOverviewCrisisTrend(_StrictMarketOverviewModel):
    requested_window_points: int
    window_points: int
    start_date: str | None
    end_date: str | None
    start_score: float | None
    end_score: float | None
    score_change: float | None
    start_percentile: float | None
    end_percentile: float | None
    percentile_change: float | None
    direction: Literal["rising", "falling", "flat", "insufficient"]


class MarketOverviewCrisisHistoryPoint(_StrictMarketOverviewModel):
    date: str
    crisis_score: float
    percentile: float | None
    available_component_count: int | None
    component_count: int | None
    available_weight: float | None
    data_status: Literal["complete", "degraded", "unavailable"] | None


class MarketOverviewCrisisRiskGate(_StrictMarketOverviewModel):
    eligible: bool
    triggered: bool
    threshold: float
    reason_code: str

    @model_validator(mode="after")
    def _trigger_requires_eligibility(self) -> MarketOverviewCrisisRiskGate:
        if self.triggered and not self.eligible:
            raise ValueError("triggered Crisis risk gate must be eligible")
        return self


class MarketOverviewCrisisDependencyGate(_StrictMarketOverviewModel):
    status: Literal["blocked", "unknown"]
    blocked_by: list[str]
    reason_code: str


class MarketOverviewCrisisInputEvidenceItem(_StrictMarketOverviewModel):
    field: str
    label: str
    aliases: list[str]
    warning: str | None
    required: bool
    available: bool
    row_count: int
    latest_date: str | None
    series_id: str | None
    source: str | None
    stale: bool | None
    stale_days: int | None


class MarketOverviewCrisisInputEvidence(_StrictMarketOverviewModel):
    inputs: list[MarketOverviewCrisisInputEvidenceItem]
    missing_inputs: list[str]
    stale_inputs: list[str]
    sources: list[str]
    latest_dates: list[str]


class MarketOverviewCrisis(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    report_date: str | None
    requested_report_date: str | None
    rule_version: str | None
    score: float | None
    current_available: bool
    history_only: bool
    regime: str | None
    percentile: float | None
    data_status: Literal["complete", "degraded", "unavailable"]
    score_trend: MarketOverviewCrisisTrend
    score_trends: list[MarketOverviewCrisisTrend]
    score_history: list[MarketOverviewCrisisHistoryPoint]
    warnings: list[str]
    available_component_count: int | None
    component_count: int | None
    input_evidence: MarketOverviewCrisisInputEvidence
    dependency_gate: MarketOverviewCrisisDependencyGate | None
    delta: MarketOverviewCrisisDelta
    risk_gate: MarketOverviewCrisisRiskGate


class MarketOverviewSignalCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    kind: Literal["ops_status", "market_signal"]
    title: str | None = None
    stance: str | None = None
    tone: str | None = None
    score: float | None = None
    evidence: list[str] = Field(default_factory=list)


class MarketOverviewSignals(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    cards: list[MarketOverviewSignalCard]


class MarketOverviewNewsSample(_StrictMarketOverviewModel):
    requested: int
    returned: int
    total_rows: int
    excluded_future_rows: int
    latest_received_at: str | None
    stale_days: int | None


class MarketOverviewNewsGranularity(_StrictMarketOverviewModel):
    datetime_rows: int
    date_only_rows: int


class MarketOverviewNewsTopic(_StrictMarketOverviewModel):
    key: str
    label: str
    cells: list[int]


class MarketOverviewNewsDensity(_StrictMarketOverviewModel):
    tz: str
    bucket_hours: int
    topics: list[MarketOverviewNewsTopic]
    max_count: int


class MarketOverviewNewsLatestItem(_StrictMarketOverviewModel):
    event_key: str | None
    received_at: str
    topic_code: str | None
    group_id: str | None
    summary: str | None


class MarketOverviewNewsCompare(_StrictMarketOverviewModel):
    same_direction: int
    conflicting: int
    review_needed: int
    candidate_scenarios: int
    review_items: list[dict[str, Any]]


class MarketOverviewNews(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    sample: MarketOverviewNewsSample
    granularity: MarketOverviewNewsGranularity
    density: MarketOverviewNewsDensity
    latest: list[MarketOverviewNewsLatestItem]
    compare: MarketOverviewNewsCompare


class MarketOverviewAction(_StrictMarketOverviewModel):
    priority: Literal["P0", "P1", "P2"]
    key: str
    label: str
    route: str
    basis: str
    evidence: dict[str, Any]


class MarketOverviewActions(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    items: list[MarketOverviewAction]


class MarketOverviewCharts(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    reason: str | None
    choice_latest: ChoiceMacroLatestPayload | None
    market_rates: ChoiceMacroLatestPayload | None


class MarketObservationPoint(_StrictMarketOverviewModel):
    trade_date: str
    value_numeric: float | None


class MarketObservationEvidence(_StrictMarketOverviewModel):
    key: str
    label: str
    series_id: str
    value: float | None
    unit: str
    observation_date: str | None
    source: str | None
    quality_flag: str
    fallback_mode: str
    is_proxy: bool
    previous_value: float | None
    previous_date: str | None
    change_bp: float | None
    status: MarketOverviewPartitionStatus
    reason: str | None
    tenor_years: int | None = None
    recent_points: list[MarketObservationPoint]


class MarketObservationBase(_StrictMarketOverviewModel):
    status: MarketOverviewPartitionStatus
    judgment_allowed: bool
    observation_date: str | None
    comparison_date: str | None
    summary: str
    interpretation: str
    limitations: list[str]
    reason: str | None
    rule_version: str
    evidence: list[MarketObservationEvidence]
    rows: list[MarketObservationEvidence]
    verification_route: str
    window_label: str


class MarketPolicyReference(_StrictMarketOverviewModel):
    value: float | None
    unit: str
    effective_from: str | None
    effective_to: str | None
    validity_status: Literal["verified", "unverified"]
    source: str | None
    reason: str | None


class MarketFundingObservation(MarketObservationBase):
    policy_reference: MarketPolicyReference
    policy_deviation_bp: float | None


class MarketObservationSpread(_StrictMarketOverviewModel):
    key: str
    label: str
    value_bp: float | None
    previous_value_bp: float | None
    change_bp: float | None
    observation_date: str | None
    comparison_date: str | None
    status: MarketOverviewPartitionStatus
    reason: str | None
    input_keys: list[str]


class MarketRatesObservation(MarketObservationBase):
    curve_family: str
    full_curve_comparison_allowed: bool
    spreads: list[MarketObservationSpread]


class MarketOverviewSnapshotResult(_StrictMarketOverviewModel):
    funding_observation: MarketFundingObservation | None = None
    rates_observation: MarketRatesObservation | None = None
    components: dict[str, MarketOverviewComponent]
    gate: MarketOverviewGate | None = None
    dates: MarketOverviewDates | None = None
    tape: MarketOverviewTape | None = None
    pulse: MarketOverviewPulse | None = None
    crisis: MarketOverviewCrisis | None = None
    signals: MarketOverviewSignals | None = None
    news: MarketOverviewNews | None = None
    actions: MarketOverviewActions | None = None
    charts: MarketOverviewCharts | None = None


class MarketOverviewSnapshotEnvelope(_StrictMarketOverviewModel):
    result_meta: ResultMeta
    result: MarketOverviewSnapshotResult
