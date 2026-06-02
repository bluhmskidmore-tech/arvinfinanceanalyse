from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.app.repositories.governance_repo import GovernanceRepository

AGENT_AUDIT_STREAM = "agent_audit"


class AgentAuditPayload(BaseModel):
    user_id: str
    query_text: str
    tools_used: list[str] = Field(default_factory=list)
    tables_used: list[str] = Field(default_factory=list)
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    result_meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def append_agent_audit(
    repo: GovernanceRepository, payload: AgentAuditPayload
) -> str:
    return str(repo.append(AGENT_AUDIT_STREAM, payload.model_dump(mode="json")))

