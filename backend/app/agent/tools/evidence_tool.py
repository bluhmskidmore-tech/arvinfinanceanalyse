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
        sql_executed: list[str] | None = None,
        evidence_strength: str | None = None,
    ) -> AgentEvidence:
        disclosed_sql = self._disclosed_read_only_sql(sql_executed)
        resolved_strength = str(evidence_strength or "").strip() or (
            "governed_moss"
            if tables_used or disclosed_sql or int(row_count) > 0
            else "local_fallback"
        )
        return AgentEvidence(
            tables_used=list(tables_used),
            filters_applied=dict(filters_applied),
            sql_executed=disclosed_sql,
            evidence_rows=max(int(row_count), 0),
            quality_flag=str(quality_flag or "warning"),
            evidence_strength=resolved_strength,
        )

    @staticmethod
    def _disclosed_read_only_sql(statements: list[str] | None) -> list[str]:
        # 仅用于披露：只保留 SELECT / WITH 开头的只读语句，绝不披露（更不会执行）任何写语句。
        disclosed: list[str] = []
        for statement in statements or []:
            text = " ".join(str(statement or "").split())
            if text and text.lower().startswith(("select", "with")):
                disclosed.append(text)
        return disclosed
