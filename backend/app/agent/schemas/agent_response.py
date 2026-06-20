from __future__ import annotations

from typing import Any

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, Field, model_validator


class AgentDrill(BaseModel):
    dimension: str
    label: str


class AgentSuggestedAction(BaseModel):
    type: str
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
    confirmation_token: str | None = None


class AgentCard(BaseModel):
    type: str
    title: str
    value: str | None = None
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    spec: dict[str, Any] | None = None


class AgentEvidence(BaseModel):
    tables_used: list[str] = Field(default_factory=list)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    sql_executed: list[str] = Field(default_factory=list)
    evidence_rows: int = 0
    quality_flag: str = "warning"
    evidence_strength: str = "governed_moss"

    @model_validator(mode="after")
    def _downgrade_provider_runtime_quality(self) -> AgentEvidence:
        if self.evidence_strength == "provider_runtime" and self.quality_flag == "ok":
            self.quality_flag = "warning"
        return self


class AgentResultMeta(ResultMeta):
    tables_used: list[str] = Field(default_factory=list)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    sql_executed: list[str] = Field(default_factory=list)
    evidence_rows: int = 0
    evidence_strength: str = "governed_moss"
    next_drill: list[AgentDrill] = Field(default_factory=list)

    @model_validator(mode="after")
    def _downgrade_provider_runtime_quality(self) -> AgentResultMeta:
        if self.evidence_strength == "provider_runtime" and self.quality_flag == "ok":
            self.quality_flag = "warning"
        return self


class AgentEnvelope(BaseModel):
    answer: str
    cards: list[AgentCard] = Field(default_factory=list)
    evidence: AgentEvidence
    result_meta: AgentResultMeta
    next_drill: list[AgentDrill] = Field(default_factory=list)
    suggested_actions: list[AgentSuggestedAction] = Field(default_factory=list)


class AgentDisabledResponse(BaseModel):
    enabled: bool = False
    phase: str = "phase1"
    detail: str = "Agent endpoint is planned but disabled in Phase 1."
