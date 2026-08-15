from __future__ import annotations

import logging

from backend.app.agent.schemas.agent_response import AgentEvidence

_LOGGER = logging.getLogger(__name__)

# evidence.quality_flag 在 envelope 收尾时会覆盖 result_meta.quality_flag，
# 值域必须落在 ResultMeta 的 Literal（同时是前端 ApiQuality 枚举的子集）内；
# handler 笔误产生的枚举外值在此归一化为 warning 并记日志，不再原样透传。
_QUALITY_FLAG_CONTRACT = frozenset({"ok", "warning", "error", "stale"})


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
            quality_flag=self._normalized_quality_flag(quality_flag),
            evidence_strength=resolved_strength,
        )

    @staticmethod
    def _normalized_quality_flag(quality_flag: str) -> str:
        normalized = str(quality_flag or "warning").strip().lower() or "warning"
        if normalized not in _QUALITY_FLAG_CONTRACT:
            _LOGGER.warning(
                "Agent evidence quality_flag %r is outside the contract enum %s; normalized to 'warning'.",
                quality_flag,
                sorted(_QUALITY_FLAG_CONTRACT),
            )
            return "warning"
        return normalized

    @staticmethod
    def _disclosed_read_only_sql(statements: list[str] | None) -> list[str]:
        # 仅用于披露：只保留 SELECT / WITH 开头的只读语句，绝不披露（更不会执行）任何写语句。
        disclosed: list[str] = []
        for statement in statements or []:
            text = " ".join(str(statement or "").split())
            if text and text.lower().startswith(("select", "with")):
                disclosed.append(text)
        return disclosed
