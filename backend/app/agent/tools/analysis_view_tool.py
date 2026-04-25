from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentCard,
    AgentDrill,
    AgentEnvelope,
    AgentResultMeta,
    AgentSuggestedAction,
)
from backend.app.agent.tools.evidence_tool import EvidenceTool
from backend.app.schemas.cube_query import CubeQueryRequest
from backend.app.services.cube_query_service import CubeQueryService

_HELP_ITEMS = [
    "GitNexus / 仓库图谱 / 代码关系 / context / processes",
    "组合概览 / 资产规模 / 总览",
    "损益 / 收益 / PnL",
    "久期 / DV01 / 风险",
    "信用 / 利差 / 集中度",
    "产品损益 / FTP",
    "桥接 / 归因 / 拆解",
    "风险张量 / KRD",
    "宏观 / 利率 / 市场",
    "新闻 / 事件",
    "cube query",
]

_INTENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("gitnexus_status", ("gitnexus", "仓库图谱", "代码图谱", "repo graph", "code graph", "影响分析", "context", "processes")),
    ("product_pnl", ("产品损益", "ftp")),
    ("pnl_bridge", ("桥接", "归因", "拆解", "bridge", "attribution")),
    ("risk_tensor", ("风险张量", "krd")),
    ("duration_risk", ("久期", "dv01", "风险", "duration")),
    ("credit_exposure", ("信用", "利差", "集中度", "credit", "spread", "concentration")),
    ("portfolio_overview", ("组合概览", "资产规模", "总览", "portfolio overview", "market value", "portfolio value", "asset size")),
    ("pnl_summary", ("损益", "收益", "pnl")),
    ("market_data", ("宏观", "利率", "市场数据", "macro", "market data", "macro data", "rates data")),
    ("news", ("新闻", "事件", "news", "headline", "latest news")),
]


class AnalysisViewTool:
    """Intent router + AgentEnvelope assembler."""

    def __init__(
        self,
        duckdb_path: str,
        governance_dir: str | None = None,
        cube_query_service: CubeQueryService | None = None,
        intent_handlers: dict[str, Callable[[AgentQueryRequest], dict[str, Any]]] | None = None,
    ) -> None:
        self._duckdb_path = duckdb_path
        self._governance_dir = governance_dir or ""
        self._cube_query_service = cube_query_service or CubeQueryService()
        self._intent_handlers = dict(intent_handlers or {})
        self._evidence = EvidenceTool()

    def execute(self, request: AgentQueryRequest) -> AgentEnvelope:
        intent = self._resolve_intent(request)
        try:
            if intent == "cube_query":
                return self._cube_query(request)
            if intent == "unknown":
                return self._unsupported_envelope(request)
            handler = self._intent_handlers.get(intent)
            if handler is None:
                return self._unsupported_envelope(request)
            return self._payload_envelope(
                request=request,
                intent=intent,
                payload=handler(request),
            )
        except Exception as exc:
            return self._error_envelope(request=request, intent=intent, detail=str(exc))

    def _resolve_intent(self, request: AgentQueryRequest) -> str:
        explicit_intent = str(request.context.get("intent") or "").strip().lower()
        if explicit_intent == "cube_query" or "cube_query" in request.context:
            return "cube_query"

        normalized = str(request.question or "").strip().lower()
        for intent, keywords in _INTENT_PATTERNS:
            if any(keyword.lower() in normalized for keyword in keywords):
                return intent
        return "unknown"

    def _cube_query(self, request: AgentQueryRequest) -> AgentEnvelope:
        payload = dict(request.context.get("cube_query") or {})
        if not payload:
            raise ValueError("cube_query intent requires context.cube_query payload.")
        payload.setdefault("basis", request.basis)

        cube_request = CubeQueryRequest(**payload)
        cube_response = self._cube_query_service.execute(cube_request, self._duckdb_path)
        table_name = CubeQueryService.table_name_for(cube_response.fact_table)
        filters_applied = {
            path.dimension: path.current_filter
            for path in cube_response.drill_paths
            if path.current_filter
        }
        next_drill = [
            AgentDrill(dimension=path.dimension, label=path.label)
            for path in cube_response.drill_paths
        ]
        suggested_actions = self._suggested_actions_from_drills(next_drill)
        evidence = self._evidence.build_evidence(
            tables_used=[table_name],
            filters_applied=filters_applied,
            row_count=len(cube_response.rows),
            quality_flag=cube_response.result_meta.quality_flag,
        )
        cube_meta = cube_response.result_meta.model_dump(mode="python")
        for key in ("tables_used", "filters_applied", "evidence_rows", "next_drill"):
            cube_meta.pop(key, None)
        result_meta = AgentResultMeta(
            **cube_meta,
            tables_used=evidence.tables_used,
            filters_applied=evidence.filters_applied,
            sql_executed=evidence.sql_executed,
            evidence_rows=evidence.evidence_rows,
            next_drill=next_drill,
        )
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=f"Retrieved {len(cube_response.rows)} row(s) from {cube_response.fact_table}.",
                cards=[
                    AgentCard(
                        type="table",
                        title=f"{cube_response.fact_table} cube query",
                        data=cube_response.rows,
                        spec={
                            "dimensions": cube_response.dimensions,
                            "measures": cube_response.measures,
                            "total_rows": cube_response.total_rows,
                        },
                    )
                ],
                evidence=evidence,
                result_meta=result_meta,
                next_drill=next_drill,
                suggested_actions=suggested_actions,
            )
        )

    def _payload_envelope(
        self,
        *,
        request: AgentQueryRequest,
        intent: str,
        payload: dict[str, Any],
    ) -> AgentEnvelope:
        cards = self._normalize_cards(payload.get("cards", []))
        next_drill = self._normalize_drills(payload.get("next_drill", []))
        suggested_actions = self._normalize_suggested_actions(
            payload.get("suggested_actions", []),
            fallback_drills=next_drill,
        )
        evidence = self._evidence.build_evidence(
            tables_used=list(payload.get("tables_used", [])),
            filters_applied=dict(payload.get("filters_applied", {})),
            row_count=int(payload.get("row_count", 0)),
            quality_flag=str(payload.get("quality_flag") or "warning"),
        )
        result_meta = AgentResultMeta(
            trace_id=str(payload.get("trace_id") or self._trace_id(f"agent.{intent}")),
            basis=str(payload.get("basis") or request.basis),
            result_kind=str(payload.get("result_kind") or f"agent.{intent}"),
            formal_use_allowed=bool(payload.get("formal_use_allowed", False)),
            source_version=str(payload.get("source_version") or "sv_agent_unknown"),
            vendor_version=str(payload.get("vendor_version") or "vv_none"),
            rule_version=str(payload.get("rule_version") or "rv_agent_mvp_v1"),
            cache_version=str(payload.get("cache_version") or f"cv_agent_{intent}_v1"),
            quality_flag=str(payload.get("quality_flag") or "warning"),
            vendor_status=str(payload.get("vendor_status") or "ok"),
            fallback_mode=str(payload.get("fallback_mode") or "none"),
            scenario_flag=bool(payload.get("scenario_flag", False)),
            tables_used=evidence.tables_used,
            filters_applied=evidence.filters_applied,
            sql_executed=evidence.sql_executed,
            evidence_rows=evidence.evidence_rows,
            next_drill=next_drill,
        )
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=str(payload.get("answer") or ""),
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=next_drill,
                suggested_actions=suggested_actions,
            )
        )

    def _unsupported_envelope(self, request: AgentQueryRequest) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="warning",
        )
        result_meta = AgentResultMeta(
            trace_id=self._trace_id("agent.unknown"),
            basis=request.basis,
            result_kind="agent.unknown",
            formal_use_allowed=False,
            source_version="sv_agent_unknown",
            vendor_version="vv_none",
            rule_version="rv_agent_mvp_v1",
            cache_version="cv_agent_unknown_v1",
            quality_flag="warning",
            scenario_flag=False,
            tables_used=[],
            filters_applied={},
            sql_executed=[],
            evidence_rows=0,
            next_drill=[],
        )
        return AgentEnvelope(
            **self._finalize_envelope(
                answer="暂不支持该类查询。当前支持：GitNexus 仓库图谱、组合概览、PnL、久期风险、信用暴露、产品损益、桥接、风险张量、宏观市场、新闻事件。",
                cards=[
                    AgentCard(
                        type="help",
                        title="Supported Queries",
                        data=[{"query_type": item} for item in _HELP_ITEMS],
                    )
                ],
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
            )
        )

    def _error_envelope(
        self,
        *,
        request: AgentQueryRequest,
        intent: str,
        detail: str,
    ) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={key: value for key, value in request.filters.items() if value not in (None, "")},
            row_count=0,
            quality_flag="warning",
        )
        result_meta = AgentResultMeta(
            trace_id=self._trace_id(f"agent.{intent}"),
            basis=request.basis,
            result_kind=f"agent.{intent}",
            formal_use_allowed=False,
            source_version="sv_agent_error",
            vendor_version="vv_none",
            rule_version="rv_agent_mvp_v1",
            cache_version=f"cv_agent_{intent}_v1",
            quality_flag="warning",
            scenario_flag=False,
            tables_used=[],
            filters_applied=evidence.filters_applied,
            sql_executed=[],
            evidence_rows=0,
            next_drill=[],
        )
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=f"{intent} 查询失败：{detail}",
                cards=[AgentCard(type="status", title="Error", value=detail)],
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
            )
        )

    def _normalize_cards(self, cards: list[Any]) -> list[AgentCard]:
        return [
            card if isinstance(card, AgentCard) else AgentCard.model_validate(card)
            for card in cards
        ]

    def _normalize_drills(self, drills: list[Any]) -> list[AgentDrill]:
        return [
            drill if isinstance(drill, AgentDrill) else AgentDrill.model_validate(drill)
            for drill in drills
        ]

    def _normalize_suggested_actions(
        self,
        actions: list[Any],
        *,
        fallback_drills: list[AgentDrill] | None = None,
    ) -> list[AgentSuggestedAction]:
        if actions:
            return [
                action
                if isinstance(action, AgentSuggestedAction)
                else AgentSuggestedAction.model_validate(action)
                for action in actions
            ]
        return self._suggested_actions_from_drills(fallback_drills or [])

    def _suggested_actions_from_drills(self, drills: list[AgentDrill]) -> list[AgentSuggestedAction]:
        return [
            AgentSuggestedAction(
                type="inspect_drill",
                label=drill.label,
                payload={"dimension": drill.dimension},
                requires_confirmation=True,
            )
            for drill in drills
        ]

    def _trace_id(self, result_kind: str) -> str:
        suffix = result_kind.replace(".", "_")
        return f"tr_{suffix}_{uuid4().hex[:12]}"

    def _finalize_envelope(
        self,
        *,
        answer: str,
        cards: list[AgentCard],
        evidence,
        result_meta,
        next_drill: list[AgentDrill],
        suggested_actions: list[AgentSuggestedAction] | None = None,
    ) -> dict[str, Any]:
        return {
            "answer": answer,
            "cards": [card.model_dump(mode="python") for card in cards],
            "evidence": evidence.model_dump(mode="python"),
            "result_meta": result_meta.model_dump(mode="python"),
            "next_drill": [drill.model_dump(mode="python") for drill in next_drill],
            "suggested_actions": [
                action.model_dump(mode="python") for action in (suggested_actions or [])
            ],
        }
