from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from backend.app.agent.runtime.financial_workflow_catalog import (
    FinancialWorkflow,
    resolve_financial_workflow,
)
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
        workflow = resolve_financial_workflow(request.question, request.context)
        if workflow is not None:
            if str(request.context.get("workflow_mode") or "").strip().lower() == "execute":
                return self._execute_workflow_envelope(request, workflow)
            return self._workflow_envelope(request, workflow)

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

    def _workflow_envelope(
        self,
        request: AgentQueryRequest,
        workflow: FinancialWorkflow,
    ) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="warning",
        )
        next_intent = workflow.mapped_intents[0] if workflow.mapped_intents else ""
        result_meta = AgentResultMeta(
            trace_id=self._trace_id(f"agent.workflow.{workflow.workflow_id}"),
            basis=request.basis,
            result_kind=f"agent.workflow.{workflow.workflow_id}",
            formal_use_allowed=False,
            source_version="sv_anthropic_financial_workflow_reference",
            vendor_version="vv_none",
            rule_version="rv_agent_financial_workflow_catalog_v1",
            cache_version=f"cv_agent_workflow_{workflow.workflow_id}_v1",
            quality_flag="warning",
            vendor_status="ok",
            fallback_mode="none",
            scenario_flag=request.basis == "scenario",
            tables_used=evidence.tables_used,
            filters_applied=evidence.filters_applied,
            sql_executed=evidence.sql_executed,
            evidence_rows=evidence.evidence_rows,
            next_drill=[],
        )
        cards = [
            AgentCard(
                type="workflow_plan",
                title="Workflow Plan",
                data={
                    "workflow_id": workflow.workflow_id,
                    "title": workflow.title,
                    "description": workflow.description,
                    "category": workflow.category,
                    "source": workflow.source,
                    "output_kind": workflow.output_kind,
                    "phase": "plan_only",
                },
            ),
            AgentCard(
                type="workflow_intents",
                title="Mapped MOSS Intents",
                data=[
                    {"order": index, "intent": intent}
                    for index, intent in enumerate(workflow.mapped_intents, start=1)
                ],
            ),
            AgentCard(
                type="governance_notes",
                title="Governance Notes",
                data=[{"note": note} for note in workflow.governance_notes],
            ),
        ]
        suggested_actions = []
        if next_intent:
            suggested_actions.append(
                AgentSuggestedAction(
                    type="execute_intent",
                    label=f"Execute first mapped intent: {next_intent}",
                    payload={
                        "intent": next_intent,
                        "workflow_id": workflow.workflow_id,
                    },
                    requires_confirmation=True,
                )
            )

        return AgentEnvelope(
            **self._finalize_envelope(
                answer=(
                    f"Identified financial workflow '{workflow.title}' ({workflow.workflow_id}). "
                    "This response is a workflow plan only, not a formal financial result. "
                    "If executed, it will use governed MOSS intents: "
                    f"{', '.join(workflow.mapped_intents)}."
                ),
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
                suggested_actions=suggested_actions,
            )
        )

    def _execute_workflow_envelope(
        self,
        request: AgentQueryRequest,
        workflow: FinancialWorkflow,
    ) -> AgentEnvelope:
        step_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []
        tables_used: list[str] = []
        filters_applied: dict[str, Any] = {}
        evidence_rows = 0
        failed_intents: list[str] = []

        for index, intent in enumerate(workflow.mapped_intents, start=1):
            handler = self._intent_handlers.get(intent)
            if handler is None:
                failed_intents.append(intent)
                step_rows.append(
                    self._workflow_step_row(
                        order=index,
                        intent=intent,
                        status="missing",
                        quality_flag="warning",
                        evidence_rows=0,
                    )
                )
                detail_rows.append(
                    {
                        "order": index,
                        "intent": intent,
                        "status": "missing",
                        "message": "No registered MOSS intent handler.",
                    }
                )
                continue

            try:
                envelope = self._payload_envelope(
                    request=request,
                    intent=intent,
                    payload=handler(request),
                )
            except Exception as exc:
                failed_intents.append(intent)
                step_rows.append(
                    self._workflow_step_row(
                        order=index,
                        intent=intent,
                        status="error",
                        quality_flag="warning",
                        evidence_rows=0,
                    )
                )
                detail_rows.append(
                    {
                        "order": index,
                        "intent": intent,
                        "status": "error",
                        "message": str(exc),
                    }
                )
                continue

            step_rows.append(
                self._workflow_step_row(
                    order=index,
                    intent=intent,
                    status="ok",
                    quality_flag=envelope.result_meta.quality_flag,
                    evidence_rows=envelope.evidence.evidence_rows,
                )
            )
            detail_rows.append(
                {
                    "order": index,
                    "intent": intent,
                    "status": "ok",
                    "answer": envelope.answer,
                    "result_kind": envelope.result_meta.result_kind,
                    "formal_use_allowed": envelope.result_meta.formal_use_allowed,
                    "source_version": envelope.result_meta.source_version,
                    "rule_version": envelope.result_meta.rule_version,
                    "tables_used": envelope.evidence.tables_used,
                    "evidence_rows": envelope.evidence.evidence_rows,
                    "card_count": len(envelope.cards),
                }
            )
            evidence_rows += envelope.evidence.evidence_rows
            for table in envelope.evidence.tables_used:
                if table not in tables_used:
                    tables_used.append(table)
            for key, value in envelope.evidence.filters_applied.items():
                filters_applied[f"{intent}.{key}"] = value
            if envelope.result_meta.quality_flag != "ok":
                failed_intents.append(intent)

        quality_flag = "warning" if failed_intents else "ok"
        evidence = self._evidence.build_evidence(
            tables_used=tables_used,
            filters_applied=filters_applied,
            row_count=evidence_rows,
            quality_flag=quality_flag,
        )
        result_meta = AgentResultMeta(
            trace_id=self._trace_id(f"agent.workflow.{workflow.workflow_id}"),
            basis=request.basis,
            result_kind=f"agent.workflow.{workflow.workflow_id}",
            formal_use_allowed=False,
            source_version="sv_anthropic_financial_workflow_reference",
            vendor_version="vv_none",
            rule_version="rv_agent_financial_workflow_catalog_v1",
            cache_version=f"cv_agent_workflow_{workflow.workflow_id}_v1",
            quality_flag=quality_flag,
            vendor_status="ok",
            fallback_mode="none",
            scenario_flag=request.basis == "scenario",
            tables_used=evidence.tables_used,
            filters_applied=evidence.filters_applied,
            sql_executed=evidence.sql_executed,
            evidence_rows=evidence.evidence_rows,
            next_drill=[],
        )
        cards = [
            AgentCard(
                type="workflow_execution",
                title="Workflow Execution Steps",
                data=step_rows,
            ),
            AgentCard(
                type="workflow_results",
                title="Mapped Intent Results",
                data=detail_rows,
            ),
            AgentCard(
                type="governance_notes",
                title="Governance Notes",
                data=[{"note": note} for note in workflow.governance_notes],
            ),
        ]

        if failed_intents:
            answer = (
                f"Executed financial workflow '{workflow.title}' ({workflow.workflow_id}) with warnings. "
                f"Failed or degraded intents: {', '.join(failed_intents)}. "
                "The workflow summary is not a formal financial result."
            )
        else:
            answer = (
                f"Executed financial workflow '{workflow.title}' ({workflow.workflow_id}) using governed MOSS intents: "
                f"{', '.join(workflow.mapped_intents)}. "
                "The workflow summary is not a formal financial result."
            )

        return AgentEnvelope(
            **self._finalize_envelope(
                answer=answer,
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
                suggested_actions=[],
            )
        )

    def _workflow_step_row(
        self,
        *,
        order: int,
        intent: str,
        status: str,
        quality_flag: str,
        evidence_rows: int,
    ) -> dict[str, Any]:
        return {
            "order": order,
            "intent": intent,
            "status": status,
            "quality_flag": quality_flag,
            "evidence_rows": evidence_rows,
        }

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
        suggested_actions = self._suggested_actions_from_drills(
            next_drill,
            page_context=request.page_context,
        )
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
            page_context=request.page_context,
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
                answer=self._business_answer(
                    conclusion=str(payload.get("answer") or ""),
                    cards=cards,
                    evidence=evidence,
                    result_meta=result_meta,
                    next_drill=next_drill,
                ),
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
            quality_flag="error",
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
            quality_flag="error",
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
        page_context: Any | None = None,
    ) -> list[AgentSuggestedAction]:
        if actions:
            return [
                action
                if isinstance(action, AgentSuggestedAction)
                else AgentSuggestedAction.model_validate(action)
                for action in actions
            ]
        return self._suggested_actions_from_drills(
            fallback_drills or [],
            page_context=page_context,
        )

    def _suggested_actions_from_drills(
        self,
        drills: list[AgentDrill],
        *,
        page_context: Any | None = None,
    ) -> list[AgentSuggestedAction]:
        page_context_payload = self._page_context_payload(page_context)
        row_summary = self._selected_row_summary(page_context_payload)
        return [
            AgentSuggestedAction(
                type="inspect_drill",
                label=self._page_aware_drill_label(drill.label, row_summary),
                payload=self._drill_action_payload(drill.dimension, page_context_payload),
                requires_confirmation=True,
            )
            for drill in drills
        ]

    def _page_context_payload(self, page_context: Any | None) -> dict[str, Any] | None:
        if page_context is None:
            return None
        if hasattr(page_context, "model_dump"):
            payload = page_context.model_dump(mode="python")
        else:
            payload = dict(page_context)
        return payload or None

    def _drill_action_payload(
        self,
        dimension: str,
        page_context_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"dimension": dimension}
        if page_context_payload is not None:
            payload["page_context"] = page_context_payload
        return payload

    def _selected_row_summary(self, page_context_payload: dict[str, Any] | None) -> str:
        if not page_context_payload:
            return ""
        selected_rows = page_context_payload.get("selected_rows") or []
        if not selected_rows or not isinstance(selected_rows[0], dict):
            return ""
        first_row = selected_rows[0]
        parts = [
            f"{key}={first_row[key]}"
            for key in ("book_id", "instrument_id", "recon_type", "status")
            if first_row.get(key) not in (None, "")
        ]
        return ", ".join(parts)

    def _page_aware_drill_label(self, label: str, row_summary: str) -> str:
        if not row_summary:
            return label
        return f"{label} for {row_summary}"

    def _business_answer(
        self,
        *,
        conclusion: str,
        cards: list[AgentCard],
        evidence,
        result_meta,
        next_drill: list[AgentDrill],
    ) -> str:
        if conclusion.startswith("结论："):
            return conclusion

        key_numbers = self._key_numbers(cards)
        evidence_text = self._evidence_text(evidence)
        boundary_text = self._boundary_text(result_meta)
        next_step_text = self._next_step_text(next_drill)
        return "\n".join(
            [
                f"结论：{conclusion or '本次查询未形成明确结论。'}",
                f"关键数字：{key_numbers}",
                f"证据：{evidence_text}",
                f"口径边界：{boundary_text}",
                f"下一步：{next_step_text}",
            ]
        )

    def _key_numbers(self, cards: list[AgentCard]) -> str:
        metric_parts = [
            f"{card.title}={card.value}"
            for card in cards
            if card.value not in (None, "")
        ]
        return "；".join(metric_parts[:6]) if metric_parts else "本次未返回可直接展示的关键数字。"

    def _evidence_text(self, evidence) -> str:
        tables = "、".join(evidence.tables_used) if evidence.tables_used else "未返回来源表"
        return f"{tables}；证据行数={evidence.evidence_rows}；质量标识={evidence.quality_flag}。"

    def _boundary_text(self, result_meta) -> str:
        filters = getattr(result_meta, "filters_applied", {}) or {}
        filter_parts = [
            f"{key}={value}"
            for key, value in filters.items()
            if value not in (None, "", [])
        ]
        filter_text = "；".join(filter_parts) if filter_parts else "未返回筛选条件"
        formal_text = "可正式使用" if result_meta.formal_use_allowed else "非正式使用"
        return f"basis={result_meta.basis}；{formal_text}；result_kind={result_meta.result_kind}；{filter_text}。"

    def _next_step_text(self, next_drill: list[AgentDrill]) -> str:
        if not next_drill:
            return "暂无系统建议下钻；可继续追问证据、口径或异常项。"
        return "；".join(drill.label for drill in next_drill)

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
