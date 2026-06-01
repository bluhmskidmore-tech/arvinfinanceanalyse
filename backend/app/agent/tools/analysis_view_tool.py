from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, cast
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
    ("duration_risk", ("久期", "dv01", "duration")),
    ("credit_exposure", ("信用", "利差", "集中度", "credit", "spread", "concentration")),
    ("portfolio_overview", ("组合概览", "资产规模", "总览", "portfolio overview", "market value", "portfolio value", "asset size")),
    ("pnl_summary", ("损益", "收益", "pnl")),
    ("market_data", ("宏观", "利率", "市场数据", "macro", "market data", "macro data", "rates data")),
    ("news", ("新闻", "事件", "news", "headline", "latest news")),
]

_PAGE_DEFAULT_INTENTS = {
    "dashboard": "portfolio_overview",
    "bond-dashboard": "portfolio_overview",
    "balance-analysis": "portfolio_overview",
    "pnl-attribution": "pnl_summary",
    "product-category-pnl": "product_pnl",
    "risk-tensor": "risk_tensor",
    "bond-analytics": "duration_risk",
    "market-data": "market_data",
    "stock-analysis": "market_data",
}

_ANALYSIS_CHAT_PATTERNS = (
    "analysis",
    "analyze",
    "explain",
    "summarize",
    "summary",
    "judge",
    "risk",
    "what does this mean",
    "continue",
    "follow up",
    "\u5206\u6790",
    "\u89e3\u91ca",
    "\u603b\u7ed3",
    "\u5224\u65ad",
    "\u98ce\u9669",
    "\u7ed3\u8bba",
    "\u8bf4\u660e",
    "\u7ee7\u7eed",
    "\u8ffd\u95ee",
)

_GOVERNED_PATHS = (
    ("portfolio_overview", "Portfolio overview"),
    ("pnl_summary", "PnL summary"),
    ("duration_risk", "Duration / DV01"),
    ("credit_exposure", "Credit exposure"),
    ("product_pnl", "Product PnL"),
    ("pnl_bridge", "PnL bridge"),
    ("risk_tensor", "Risk tensor"),
    ("market_data", "Market data"),
    ("news", "News events"),
)

_GOVERNED_PATHS_ZH = (
    ("portfolio_overview", "\u7ec4\u5408\u6982\u89c8"),
    ("pnl_summary", "PnL \u6c47\u603b"),
    ("duration_risk", "\u4e45\u671f / DV01"),
    ("credit_exposure", "\u4fe1\u7528\u66b4\u9732"),
    ("product_pnl", "\u4ea7\u54c1\u635f\u76ca"),
    ("pnl_bridge", "PnL \u6865\u63a5"),
    ("risk_tensor", "\u98ce\u9669\u5f20\u91cf"),
    ("market_data", "\u5e02\u573a\u6570\u636e"),
    ("news", "\u65b0\u95fb\u4e8b\u4ef6"),
)

_LOCAL_GOVERNED_INTENTS = frozenset(intent for intent, _label in _GOVERNED_PATHS)


def is_explicit_local_agent_intent(intent: str) -> bool:
    return intent.strip().lower() in _LOCAL_GOVERNED_INTENTS


def is_plain_analysis_chat_question(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    if not normalized:
        return False
    if not any(pattern in normalized for pattern in _ANALYSIS_CHAT_PATTERNS):
        return False
    return not any(
        keyword.lower() in normalized
        for _intent, keywords in _INTENT_PATTERNS
        for keyword in keywords
    )


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
            if intent == "analysis_chat":
                return self._analysis_chat_envelope(request)
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
        if explicit_intent in self._intent_handlers:
            return explicit_intent

        normalized = str(request.question or "").strip().lower()
        for intent, keywords in _INTENT_PATTERNS:
            if intent in self._intent_handlers and any(keyword.lower() in normalized for keyword in keywords):
                return intent
        follow_up_intent = self._conversation_intent(request)
        if follow_up_intent is not None:
            return follow_up_intent
        if self._is_page_context_question(normalized):
            page_intent = self._page_default_intent(request)
            if page_intent is not None:
                return page_intent
        if self._is_analysis_chat_question(normalized):
            return "analysis_chat"
        return "unknown"

    def _conversation_intent(self, request: AgentQueryRequest) -> str | None:
        conversation = request.context.get("conversation")
        if not isinstance(conversation, dict):
            return None
        turns = conversation.get("recent_turns")
        if not isinstance(turns, list):
            return None
        for turn in reversed(turns):
            if not isinstance(turn, dict):
                continue
            for value in (turn.get("result_kind"), turn.get("trace_id"), turn.get("answer")):
                intent = self._intent_from_text(value)
                if intent is not None:
                    return intent
        return None

    def _intent_from_text(self, value: Any) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        for intent in self._intent_handlers:
            if f"agent.{intent}" in text:
                return intent
        return None

    def _page_default_intent(self, request: AgentQueryRequest) -> str | None:
        if request.page_context is None:
            return None
        page_id = request.page_context.page_id.strip().lower()
        intent = _PAGE_DEFAULT_INTENTS.get(page_id)
        if intent in self._intent_handlers:
            return intent
        return None

    def _is_page_context_question(self, normalized_question: str) -> bool:
        if not normalized_question:
            return False
        return any(
            token in normalized_question
            for token in (
                "当前页",
                "当前页面",
                "这个页面",
                "本页",
                "页面",
                "current page",
                "this page",
            )
        )

    def _is_analysis_chat_question(self, normalized_question: str) -> bool:
        return is_plain_analysis_chat_question(normalized_question)

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

        quality_flag: Literal["ok", "warning", "error", "stale"] = "warning" if failed_intents else "ok"
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

    def _analysis_chat_envelope(self, request: AgentQueryRequest) -> AgentEnvelope:
        filters_applied = self._analysis_chat_filters(request)
        is_chinese = self._is_chinese_text(request.question)
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied=filters_applied,
            row_count=0,
            quality_flag="warning",
        )
        result_meta = AgentResultMeta(
            trace_id=self._trace_id("agent.analysis_chat"),
            basis=request.basis,
            result_kind="agent.analysis_chat",
            formal_use_allowed=False,
            source_version="sv_agent_local_analysis_chat",
            vendor_version="vv_none",
            rule_version="rv_agent_local_analysis_chat_v1",
            cache_version="cv_agent_local_analysis_chat_v1",
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
                type="status",
                title="\u672c\u5730\u5206\u6790\u5bf9\u8bdd" if is_chinese else "Local Analysis Conversation",
                value=(
                    "\u672a\u5339\u914d\u53d7\u6cbb\u7406\u6307\u6807 intent\uff0c\u672c\u5730 Agent "
                    "\u672a\u8fd0\u884c\u6b63\u5f0f\u6307\u6807\u67e5\u8be2\uff0c\u4e5f\u4e0d\u4f1a\u7f16\u9020\u6570\u5b57\u3002"
                    if is_chinese
                    else (
                        "No governed metric intent matched this turn, so the local agent did not run a formal "
                        "metric query or invent figures."
                    )
                ),
            ),
            AgentCard(
                type="help",
                title="\u53ef\u7ee7\u7eed\u67e5\u8be2\u7684\u6cbb\u7406\u8def\u5f84" if is_chinese else "Available Governed Paths",
                data=[
                    {"intent": intent, "label": label}
                    for intent, label in self._governed_paths(is_chinese=is_chinese)
                    if not self._intent_handlers or intent in self._intent_handlers
                ],
            ),
        ]
        if filters_applied:
            cards.append(
                AgentCard(
                    type="context",
                    title="\u5df2\u6355\u83b7\u4e0a\u4e0b\u6587" if is_chinese else "Captured Context",
                    data=filters_applied,
                )
            )
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=self._analysis_chat_answer(request, filters_applied),
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
                suggested_actions=self._analysis_chat_suggested_actions(is_chinese=is_chinese),
            )
        )

    def _analysis_chat_filters(self, request: AgentQueryRequest) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        page_context = self._page_context_payload(request.page_context)
        if page_context:
            page_id = str(page_context.get("page_id") or "").strip()
            if page_id:
                filters["page_id"] = page_id
            current_filters = page_context.get("current_filters")
            if isinstance(current_filters, dict):
                for key in ("report_date", "as_of_date", "date"):
                    value = current_filters.get(key)
                    if value not in (None, ""):
                        filters["report_date"] = value
                        break
            selected_rows = page_context.get("selected_rows")
            if isinstance(selected_rows, list) and selected_rows:
                filters["selected_rows"] = len(selected_rows)

        conversation = request.context.get("conversation")
        if isinstance(conversation, dict):
            recent_turns = conversation.get("recent_turns")
            if isinstance(recent_turns, list) and recent_turns:
                filters["conversation_turns"] = len(recent_turns)
                latest = recent_turns[-1]
                if isinstance(latest, dict) and latest.get("result_kind"):
                    filters["latest_result_kind"] = latest["result_kind"]
        return filters

    def _analysis_chat_answer(
        self,
        request: AgentQueryRequest,
        filters_applied: dict[str, Any],
    ) -> str:
        context_bits: list[str] = []
        if "page_id" in filters_applied:
            context_bits.append(f"page={filters_applied['page_id']}")
        if "report_date" in filters_applied:
            context_bits.append(f"report_date={filters_applied['report_date']}")
        if "conversation_turns" in filters_applied:
            context_bits.append(f"recent_turns={filters_applied['conversation_turns']}")
        context_text = ", ".join(context_bits) if context_bits else "no page or prior-turn context"
        if self._is_chinese_text(request.question):
            chinese_context_text = context_text if context_bits else "\u672a\u6355\u83b7\u5230\u9875\u9762\u6216\u4e0a\u4e00\u8f6e\u4e0a\u4e0b\u6587"
            return (
                "\u672c\u5730\u5206\u6790\u5bf9\u8bdd\u5df2\u63a5\u4f4f\u8fd9\u4e00\u8f6e\u95ee\u9898\uff0c"
                "\u4f46\u672a\u8fd0\u884c\u6b63\u5f0f\u6307\u6807\u67e5\u8be2\uff0c\u4e5f\u4e0d\u4f1a\u7f16\u9020\u6570\u5b57\u3002"
                "\u8fd9\u4e00\u8f6e\u53ea\u80fd\u4f5c\u4e3a\u5206\u6790\u5f15\u5bfc\uff0c\u4e0d\u80fd\u4f5c\u4e3a\u6b63\u5f0f\u91d1\u878d\u7ed3\u8bba\u3002"
                f"\u5df2\u6355\u83b7\u4e0a\u4e0b\u6587\uff1a{chinese_context_text}\u3002"
                "\u5982\u679c\u9700\u8981\u6570\u5b57\u548c\u8bc1\u636e\uff0c\u8bf7\u7ee7\u7eed\u6307\u5b9a\u4e00\u6761\u53d7\u6cbb\u7406\u8def\u5f84\uff1a"
                "\u7ec4\u5408\u6982\u89c8\u3001PnL \u6c47\u603b\u3001\u4e45\u671f/DV01\u3001\u4fe1\u7528\u66b4\u9732\u3001"
                "\u4ea7\u54c1\u635f\u76ca\u3001PnL \u6865\u63a5\u3001\u98ce\u9669\u5f20\u91cf\u3001\u5e02\u573a\u6570\u636e\u6216\u65b0\u95fb\u4e8b\u4ef6\u3002"
            )
        return (
            "I can keep this as a local analysis conversation, but I did not run a formal metric query. "
            "The current turn matched analysis intent rather than a governed metric path, so this response "
            "cannot be used as a formal financial conclusion. "
            f"Captured context: {context_text}. "
            "For numbers or evidence, ask for one governed path such as portfolio overview, PnL summary, "
            "duration/DV01, credit exposure, product PnL, PnL bridge, risk tensor, market data, or news."
        )

    def _is_chinese_text(self, value: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in value)

    def _governed_paths(self, *, is_chinese: bool) -> tuple[tuple[str, str], ...]:
        return _GOVERNED_PATHS_ZH if is_chinese else _GOVERNED_PATHS

    def _analysis_chat_suggested_actions(self, *, is_chinese: bool) -> list[AgentSuggestedAction]:
        return [
            AgentSuggestedAction(
                type="execute_intent",
                label=label,
                payload={"intent": intent},
                requires_confirmation=True,
            )
            for intent, label in self._governed_paths(is_chinese=is_chinese)[:3]
        ]

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
            basis=cast(Literal["formal", "scenario", "analytical", "ledger"], payload.get("basis") or request.basis),
            result_kind=str(payload.get("result_kind") or f"agent.{intent}"),
            formal_use_allowed=bool(payload.get("formal_use_allowed", False)),
            source_version=str(payload.get("source_version") or "sv_agent_unknown"),
            vendor_version=str(payload.get("vendor_version") or "vv_none"),
            rule_version=str(payload.get("rule_version") or "rv_agent_mvp_v1"),
            cache_version=str(payload.get("cache_version") or f"cv_agent_{intent}_v1"),
            quality_flag=cast(Literal["ok", "warning", "error", "stale"], payload.get("quality_flag") or "warning"),
            vendor_status=cast(
                Literal["ok", "vendor_stale", "vendor_unavailable"],
                payload.get("vendor_status") or "ok",
            ),
            fallback_mode=cast(Literal["none", "latest_snapshot"], payload.get("fallback_mode") or "none"),
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
