from __future__ import annotations

from typing import Literal

from backend.app.agent.schemas.agent_response import AgentEnvelope, AgentResultMeta
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentProjectCreateRequest(_StrictWorkspaceRequest):
    name: str = Field(..., min_length=1, max_length=80)
    default_scope: str = Field(default="all", min_length=1, max_length=128)
    default_currency_basis: str = Field(default="CNY", min_length=1, max_length=32)

    @field_validator("name", "default_scope", "default_currency_basis")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class AgentProjectUpdateRequest(_StrictWorkspaceRequest):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    archived: bool | None = None

    @field_validator("name")
    @classmethod
    def _normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @model_validator(mode="after")
    def _require_change(self) -> AgentProjectUpdateRequest:
        if self.name is None and self.archived is None:
            raise ValueError("at least one project field must be provided")
        return self


class AgentProject(BaseModel):
    # Persisted entity: tolerate unknown fields so records written by newer
    # code versions stay readable after a rollback. Request DTOs above keep
    # extra="forbid" to reject owner spoofing.
    model_config = ConfigDict(extra="ignore")

    project_id: str
    owner_user_id: str
    name: str
    default_scope: str = "all"
    default_currency_basis: str = "CNY"
    archived_at: str | None = None
    created_at: str
    updated_at: str


class AgentProjectListResponse(BaseModel):
    items: list[AgentProject] = Field(default_factory=list)
    corrupt_records: int = Field(default=0, ge=0)


class AgentConversationCreateRequest(_StrictWorkspaceRequest):
    title: str = Field(..., min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class AgentConversation(BaseModel):
    # Persisted entity: tolerate unknown fields (see AgentProject).
    model_config = ConfigDict(extra="ignore")

    conversation_id: str
    project_id: str
    owner_user_id: str
    title: str
    last_run_id: str | None = None
    created_at: str
    updated_at: str


class AgentConversationListResponse(BaseModel):
    items: list[AgentConversation] = Field(default_factory=list)
    corrupt_records: int = Field(default=0, ge=0)


AgentMessageRole = Literal["user", "assistant", "system_notice"]


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    conversation_id: str
    role: AgentMessageRole
    content: str
    run_id: str
    artifact_refs: list[str] = Field(default_factory=list)
    created_at: str
    result: AgentEnvelope | None = None


class AgentMessageListResponse(BaseModel):
    items: list[AgentMessage] = Field(default_factory=list)
    corrupt_records: int = Field(default=0, ge=0)


class AgentArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    conversation_id: str
    run_id: str
    kind: Literal["agent_envelope"] = "agent_envelope"
    title: str
    content: AgentEnvelope
    result_meta: AgentResultMeta
    created_at: str


class AgentArtifactListResponse(BaseModel):
    items: list[AgentArtifact] = Field(default_factory=list)
    corrupt_records: int = Field(default=0, ge=0)
