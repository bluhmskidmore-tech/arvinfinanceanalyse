from __future__ import annotations

from backend.app.agent.schemas.agent_request import AgentQueryRequest


class EvidenceTool:
    """Target-state evidence projection tool."""

    def execute(self, request: AgentQueryRequest) -> None:
        raise RuntimeError(
            "EvidenceTool is planned for a later phase and is not executable in Phase 1."
        )

