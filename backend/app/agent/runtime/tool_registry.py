from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.agent.tools.analysis_view_tool import AnalysisViewTool
from backend.app.agent.tools.evidence_tool import EvidenceTool


class ToolRegistry:
    def __init__(
        self,
        duckdb_path: str,
        governance_dir: str,
        intent_handlers: dict[str, Callable[[AgentQueryRequest], dict[str, Any]]] | None = None,
    ) -> None:
        self._analysis_view = AnalysisViewTool(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            intent_handlers=intent_handlers,
        )
        self._evidence = EvidenceTool()

    def execute_query(self, request: AgentQueryRequest) -> AgentEnvelope:
        return self._analysis_view.execute(request)

