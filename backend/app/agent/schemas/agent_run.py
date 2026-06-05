from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.agent.schemas.agent_response import AgentEnvelope


AgentRunStatus = Literal["queued", "starting", "running", "completed", "failed"]


class AgentRunStatusResponse(BaseModel):
    run_id: str
    status: AgentRunStatus
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


class AgentRunCreateResponse(BaseModel):
    run_id: str
    status: AgentRunStatus = "queued"
    provider: str = "hermes"
    model: str = "default"
    transport: str = "bridge"
    toolsets: str = "default"
    queued_at: str


class AgentRunRecord(BaseModel):
    run_id: str
    status: AgentRunStatus
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
