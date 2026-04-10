from __future__ import annotations

from backend.app.agent.schemas.agent_request import AgentQueryRequest


class AnalysisViewTool:
    """Target-state entry point for governed analysis views."""

    def execute(self, request: AgentQueryRequest) -> None:
        raise RuntimeError(
            "AnalysisViewTool is planned for a later phase and is not executable in Phase 1."
        )

