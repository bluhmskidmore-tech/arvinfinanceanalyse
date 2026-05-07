from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LiabilityKnowledgeNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    summary: str
    why_it_matters: str
    key_questions: list[str] = Field(default_factory=list)
    source_path: str


class LiabilityKnowledgeBriefPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: str
    available: bool
    vault_path: str | None = None
    status_note: str | None = None
    notes: list[LiabilityKnowledgeNote] = Field(default_factory=list)
