from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.result_meta import ResultMeta


class AgentDrill(BaseModel):
    dimension: str
    label: str


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


class AgentResultMeta(ResultMeta):
    tables_used: list[str] = Field(default_factory=list)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    sql_executed: list[str] = Field(default_factory=list)
    evidence_rows: int = 0
    next_drill: list[AgentDrill] = Field(default_factory=list)


class AgentEnvelope(BaseModel):
    answer: str
    cards: list[AgentCard] = Field(default_factory=list)
    evidence: AgentEvidence
    result_meta: AgentResultMeta
    next_drill: list[AgentDrill] = Field(default_factory=list)


class AgentDisabledResponse(BaseModel):
    enabled: bool = False
    phase: str = "phase1"
    detail: str = "Agent endpoint is planned but disabled in Phase 1."

