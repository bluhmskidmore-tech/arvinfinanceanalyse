from __future__ import annotations

from backend.app.agent.schemas.agent_response import AgentEvidence


class EvidenceTool:
    """Projects governed evidence metadata into the Agent contract."""

    def build_evidence(
        self,
        tables_used: list[str],
        filters_applied: dict,
        row_count: int,
        quality_flag: str,
    ) -> AgentEvidence:
        return AgentEvidence(
            tables_used=list(tables_used),
            filters_applied=dict(filters_applied),
            sql_executed=[],
            evidence_rows=max(int(row_count), 0),
            quality_flag=str(quality_flag or "warning"),
        )

