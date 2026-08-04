from __future__ import annotations

from typing import Literal

from backend.app.agent.schemas.agent_response import AgentEnvelope
from pydantic import BaseModel, Field

AgentRunStatus = Literal[
    "queued",
    "starting",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class AgentRunStatusResponse(BaseModel):
    run_id: str
    status: AgentRunStatus
    conversation_id: str | None = None
    retry_of_run_id: str | None = None
    artifact_refs: list[str] | None = None
    question: str | None = None
    provider: str = "hermes"
    model: str = "default"
    transport: str = "bridge"
    toolsets: str = "default"
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    error_message: str | None = None
    result: AgentEnvelope | None = None


class AgentRunListResponse(BaseModel):
    items: list[AgentRunStatusResponse]


class AgentRunCreateResponse(BaseModel):
    run_id: str
    status: AgentRunStatus = "queued"
    conversation_id: str | None = None
    retry_of_run_id: str | None = None
    artifact_refs: list[str] | None = None
    provider: str = "hermes"
    model: str = "default"
    transport: str = "bridge"
    toolsets: str = "default"
    queued_at: str


class AgentRunRecord(BaseModel):
    run_id: str
    status: AgentRunStatus
    conversation_id: str | None = None
    retry_of_run_id: str | None = None
    artifact_refs: list[str] | None = None
    question: str
    request: dict[str, object] = Field(default_factory=dict)
    provider: str = "hermes"
    model: str = "default"
    transport: str = "bridge"
    toolsets: str = "default"
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    error_message: str | None = None
    result: dict[str, object] | None = None
