from __future__ import annotations

from pydantic import BaseModel


class KpiOwnerPayload(BaseModel):
    owner_id: int
    owner_name: str
    org_unit: str
    person_name: str | None = None
    year: int
    scope_type: str
    scope_key: dict[str, object] | None = None
    is_active: bool
    created_at: str
    updated_at: str


class KpiOwnerAuthorityMeta(BaseModel):
    """Disclosure for the KPI authority gate when the surface has no governed data.

    Present only when the owners list is intentionally empty because no
    authoritative KPI source has been loaded; absent on normal reads.
    """

    authority_status: str
    reason: str
    owner_count: int
    year: int | None = None


class KpiOwnerListPayload(BaseModel):
    owners: list[KpiOwnerPayload]
    total: int
    meta: KpiOwnerAuthorityMeta | None = None


class KpiPeriodMetricSummaryPayload(BaseModel):
    metric_id: int
    metric_code: str
    metric_name: str
    major_category: str
    indicator_category: str | None = None
    target_value: str | None = None
    unit: str | None = None
    score_weight: str
    period_actual_value: str | None = None
    period_completion_ratio: str | None = None
    period_progress_pct: str | None = None
    period_score_value: str | None = None
    period_start_date: str
    period_end_date: str
    data_date: str | None = None


class KpiPeriodSummaryPayload(BaseModel):
    owner_id: int
    owner_name: str
    year: int
    period_type: str
    period_value: int | None = None
    period_label: str
    period_start_date: str
    period_end_date: str
    metrics: list[KpiPeriodMetricSummaryPayload]
    total: int
    total_weight: str
    total_score: str
