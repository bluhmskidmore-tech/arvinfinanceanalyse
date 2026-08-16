from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeNoteBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_id: str
    title: str
    summary: str
    source_path: str
    entities: list[str]
    binding_status: Literal["narrative", "candidate"] = "narrative"
    warnings: list[str] = Field(default_factory=list)


class KnowledgeIndexPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    vault_path: str | None = None
    status_note: str | None = None
    notes: list[KnowledgeNoteBinding] = Field(default_factory=list)
    unknown_bindings: dict[str, list[str]] = Field(default_factory=dict)


class EntityNotesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    available: bool
    vault_path: str | None = None
    status_note: str | None = None
    notes: list[KnowledgeNoteBinding] = Field(default_factory=list)
