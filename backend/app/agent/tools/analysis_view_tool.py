from __future__ import annotations

import re

from collections.abc import Callable
from typing import Any, Literal, cast
from uuid import uuid4

from backend.app.agent.runtime.action_token import agent_action_confirmation_token
from backend.app.agent.runtime.financial_workflow_catalog import (
    FinancialWorkflow,
    list_financial_workflows,
)
from backend.app.agent.runtime.local_request_resolution import (
    LocalRequestResolution,
    _semantic_report_date,
    resolve_local_request,
)
from backend.app.agent.runtime.local_request_resolution import (
    has_explicit_local_agent_context as _has_explicit_local_agent_context,
)
from backend.app.agent.runtime.local_request_resolution import (
    is_explicit_local_agent_intent as _is_explicit_local_agent_intent,
)
from backend.app.agent.runtime.local_request_resolution import (
    is_plain_analysis_chat_question as _is_plain_analysis_chat_question,
)
from backend.app.agent.runtime.ontology_bindings import (
    ONTOLOGY_BINDING_REVISION,
    ontology_content_revision,
    ontology_reference_payload,
)
from backend.app.agent.runtime.research_workflow_catalog import (
    ResearchWorkflow,
    list_research_workflows,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentCard,
    AgentDrill,
    AgentEnvelope,
    AgentResultMeta,
    AgentSemanticContext,
    AgentSemanticReference,
    AgentSuggestedAction,
)
from backend.app.agent.tools.evidence_tool import EvidenceTool
from backend.app.schemas.cube_query import CubeQueryRequest
from backend.app.schemas.result_meta import SourceSurface
from backend.app.services.cube_query_service import CubeQueryService


def _safe_execution_error_detail(exc: Exception) -> str:
    """Keep controlled error categories while withholding source-bearing exception text."""
    message = str(exc)
    detail = "Analysis execution failed."
    if isinstance(exc, ValueError):
        if message == "No governed report dates are available for this query.":
            detail = "No governed report dates are available for this query."
        elif message.startswith("GitNexus repo_path is outside allowed roots: "):
            detail = "GitNexus repo_path is outside allowed roots."
        else:
            date_error = re.fullmatch(
                r"Requested report_date=(\d{4}-\d{2}-\d{2}) is not in available governed dates "
                r"\[(?:'\d{4}-\d{2}-\d{2}'(?:, )?)*\]\.",
                message,
            )
            if date_error is not None:
                detail = f"Requested report_date={date_error.group(1)} is not in available governed dates."
    elif isinstance(exc, RuntimeError):
        if message == "Formal pnl storage is unavailable.":
            detail = "Formal pnl storage is unavailable."
        elif message == (
            "agent action confirmation token requires a non-empty "
            "payload.confirmation_scope.user_id; refusing to issue an unbound "
            "token (fail-closed). Ensure the request context carries the "
            "authenticated user_id."
        ):
            detail = "Action confirmation requires payload.confirmation_scope.user_id (fail-closed)."
    return f"{detail} (error_type={type(exc).__name__})"


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

# 意图/页面/分析话术模式表的唯一权威来源是
# backend/app/agent/runtime/local_request_resolution.py；本文件不再持有副本。

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

def is_explicit_local_agent_intent(intent: str) -> bool:
    return _is_explicit_local_agent_intent(intent)


def has_explicit_local_agent_context(context: dict[str, Any] | None) -> bool:
    return _has_explicit_local_agent_context(context)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _requested_report_date(request: AgentQueryRequest) -> str | None:
    current_filters = request.context.get("current_filters")
    if not isinstance(current_filters, dict):
        current_filters = {}
    page_current_filters = request.page_context.current_filters if request.page_context else {}
    selected = next((
        container[key]
        for key in ("report_date", "date")
        for container in (request.filters, request.context, current_filters, page_current_filters)
        if container.get(key) is not None and str(container[key]).strip()
    ), None)
    # Match the local handlers while retaining the existing filter precedence.
    date_request = AgentQueryRequest(
        question=request.question,
        filters={"report_date": selected} if selected is not None else {},
    )
    report_date, error = _semantic_report_date(date_request, request.question)
    if error is not None:
        raise ValueError(error)
    return report_date


def _request_with_report_date(
    request: AgentQueryRequest,
    report_date: str,
) -> AgentQueryRequest:
    context = dict(request.context)
    context["report_date"] = report_date
    return request.model_copy(update={"context": context})


def is_plain_analysis_chat_question(question: str) -> bool:
    return _is_plain_analysis_chat_question(question)


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
        # governance_dir 仅为构造兼容保留；audit 挂接发生在 service 层。
        self._governance_dir = governance_dir or ""
        self._cube_query_service = cube_query_service or CubeQueryService()
        self._intent_handlers = dict(intent_handlers or {})
        self._evidence = EvidenceTool()
        # 当前请求的确认 token 作用域（user/run），在每次 execute 开头刷新。
        self._action_scope: dict[str, str] | None = None

    def _result_meta(
        self,
        *,
        request: AgentQueryRequest,
        result_kind: str,
        formal_use_allowed: bool,
        source_version: str,
        rule_version: str,
        cache_version: str,
        quality_flag: Literal["ok", "warning", "error", "stale"],
        evidence: Any,
        trace_id: str | None = None,
        basis: Literal["formal", "scenario", "analytical", "ledger"] | None = None,
        amount_currency_basis: str | None = None,
        amount_currency_basis_note: str | None = None,
        vendor_version: str = "vv_none",
        cache_key: str | None = None,
        vendor_status: Literal["ok", "vendor_stale", "vendor_unavailable"] = "ok",
        fallback_mode: Literal["none", "latest_snapshot"] = "none",
        requested_report_date: str | None = None,
        resolved_report_date: str | None = None,
        scenario_flag: bool | None = None,
        as_of_date: str | None = None,
        date_basis: str | None = None,
        fallback_date: str | None = None,
        tables_used: list[str] | None = None,
        filters_applied: dict[str, Any] | None = None,
        sql_executed: list[str] | None = None,
        evidence_rows: int | None = None,
        next_drill: list[AgentDrill] | None = None,
        source_surface: SourceSurface | None = None,
        generated_at: Any | None = None,
        data_built_at: Any | None = None,
    ) -> AgentResultMeta:
        optional_fields: dict[str, Any] = {}
        if generated_at is not None:
            optional_fields["generated_at"] = generated_at
        if data_built_at is not None:
            optional_fields["data_built_at"] = data_built_at
        return AgentResultMeta(
            trace_id=trace_id or self._trace_id(result_kind),
            basis=basis or request.basis,
            result_kind=result_kind,
            formal_use_allowed=formal_use_allowed,
            amount_currency_basis=amount_currency_basis,
            amount_currency_basis_note=amount_currency_basis_note,
            source_version=source_version,
            vendor_version=vendor_version,
            rule_version=rule_version,
            cache_version=cache_version,
            cache_key=cache_key,
            quality_flag=quality_flag,
            vendor_status=vendor_status,
            fallback_mode=fallback_mode,
            requested_report_date=requested_report_date,
            resolved_report_date=resolved_report_date,
            scenario_flag=request.basis == "scenario" if scenario_flag is None else scenario_flag,
            as_of_date=as_of_date,
            date_basis=date_basis,
            fallback_date=fallback_date,
            tables_used=evidence.tables_used if tables_used is None else tables_used,
            filters_applied=evidence.filters_applied if filters_applied is None else filters_applied,
            sql_executed=evidence.sql_executed if sql_executed is None else sql_executed,
            evidence_rows=evidence.evidence_rows if evidence_rows is None else evidence_rows,
            next_drill=[] if next_drill is None else next_drill,
            source_surface=source_surface,
            **optional_fields,
        )

    def execute(self, request: AgentQueryRequest) -> AgentEnvelope:
        self._action_scope = self._confirmation_scope(request)
        scope_violation = self._suggested_action_scope_violation(request)
        if scope_violation is not None:
            return self._error_envelope(
                request=request,
                intent="action_scope",
                detail=scope_violation,
            )
        resolution = resolve_local_request(request)
        if resolution.reason == "unknown_workflow":
            return self._unknown_workflow_envelope(request)
        if resolution.semantic_status == "clarification_required":
            return self._semantic_clarification_envelope(request, resolution)
        if resolution.semantic_status == "unsupported":
            return self._semantic_unsupported_envelope(request, resolution)
        if resolution.semantic_status == "unavailable":
            return self._semantic_unavailable_envelope(request, resolution)
        if resolution.semantic_operation == "definition":
            return self._semantic_definition_envelope(request, resolution)

        workflow_mode = str(request.context.get("workflow_mode") or "").strip().lower()
        workflow = resolution.financial_workflow
        if workflow is not None:
            mode_violation = self._workflow_mode_violation(workflow_mode)
            if mode_violation is not None:
                return self._error_envelope(
                    request=request,
                    intent=f"workflow.{workflow.workflow_id}",
                    detail=mode_violation,
                )
            if workflow_mode == "execute":
                return self._execute_workflow_envelope(request, workflow)
            return self._workflow_envelope(request, workflow)

        research_workflow = resolution.research_workflow
        if research_workflow is not None:
            mode_violation = self._workflow_mode_violation(workflow_mode)
            if mode_violation is not None:
                return self._error_envelope(
                    request=request,
                    intent=f"workflow.{research_workflow.workflow_id}",
                    detail=mode_violation,
                )
            explicit_intent = str(request.context.get("intent") or "").strip().lower().replace("-", "_")
            # 显式 context.intent 保持既有直接执行语义；其余入口与 financial workflow 对齐：默认 plan，execute 需显式声明。
            if workflow_mode == "execute" or explicit_intent == research_workflow.workflow_id:
                return self._execute_research_workflow(request, research_workflow)
            return self._research_workflow_plan_envelope(request, research_workflow)

        intent = resolution.intent or "unknown"
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
        except Exception as exc:  # noqa: BLE001 - Arbitrary read-only handlers must return an error envelope with formal use denied.
            semantic_reason_code = None
            if resolution.semantic_operation == "value" and (
                isinstance(exc, ValueError)
                or (
                    isinstance(exc, RuntimeError)
                    and str(exc).strip() == "Formal pnl storage is unavailable."
                )
            ):
                semantic_reason_code = "upstream_data_unavailable"
            return self._error_envelope(
                request=request,
                intent=intent,
                detail=_safe_execution_error_detail(exc),
                semantic_reason_code=semantic_reason_code,
            )

    def _semantic_definition_envelope(
        self,
        request: AgentQueryRequest,
        resolution: LocalRequestResolution,
    ) -> AgentEnvelope:
        references = self._semantic_references(resolution)
        if not references:
            return self._semantic_unavailable_envelope(request, resolution)
        reference = references[0]
        authority = "、".join(reference.authority) if reference.authority else "未提供出处"
        detail_parts = [reference.business_definition]
        if reference.unit:
            detail_parts.append(f"单位：{reference.unit}")
        if reference.time_semantics:
            detail_parts.append(f"时间语义：{reference.time_semantics}")
        detail_parts.append(f"出处：{authority}")
        answer = "；".join(detail_parts) + "。"
        return self._semantic_no_data_envelope(
            request=request,
            resolution=resolution,
            answer=answer,
            cards=[
                AgentCard(
                    type="metric_definition",
                    title=reference.name,
                    data=reference.model_dump(mode="python"),
                    metric_id=reference.entity_id,
                )
            ],
            result_kind="agent.ontology_definition",
            result_check="not_applicable",
            references=references,
        )

    def _semantic_clarification_envelope(
        self,
        request: AgentQueryRequest,
        resolution: LocalRequestResolution,
    ) -> AgentEnvelope:
        references = self._semantic_references(resolution)
        reason_code = resolution.semantic_reason_code or "clarification_required"
        if reason_code == "report_date_required":
            answer = "请提供一个明确的 YYYY-MM-DD 报告日后再查询该指标。"
        elif reason_code in {"report_date_conflict", "invalid_report_date"}:
            answer = "报告日无效或相互冲突，请只提供一个真实的 YYYY-MM-DD 报告日。"
        elif reason_code == "operation_conflict":
            answer = "请明确本次是查看指标定义，还是查询指定报告日的指标数值。"
        elif reason_code == "operation_required":
            answer = "请明确要查看指标定义，或提供 YYYY-MM-DD 报告日查询数值。"
        elif reason_code == "explicit_intent_semantic_conflict":
            answer = "请求指定了损益取数，但问题是在询问指标定义；请移除取数 intent 后重试。"
        elif reason_code == "ambiguous_metric_alias":
            answer = "“利息收入”可能对应不同口径；请明确 514、MTR-PNL-001 或正式 PnL 范围。"
        elif reason_code == "negated_metric_reference":
            answer = "当前问题否定了已识别指标，请明确实际要查询的指标和报告日。"
        elif reason_code == "multiple_intents":
            answer = (
                "本次问题同时命中多个不同业务口径，系统未替你挑选其中一个。"
                "请明确这次要看哪一项，或分开提问。"
            )
        elif reason_code == "negated_intent_reference":
            answer = "当前问题否定了识别到的业务口径，请明确本次实际要查看的内容。"
        elif reason_code == "relative_date_requires_explicit_report_date":
            answer = (
                "“今日/昨日”等相对日期无法确定报告日，系统未取最新日期代替。"
                "请提供一个明确的 YYYY-MM-DD 报告日。"
            )
        else:
            names = "、".join(reference.name for reference in references)
            answer = (
                f"“收益”可能指 {names}。请明确指标，并在查询数值时提供 YYYY-MM-DD 报告日。"
                if names
                else "请明确要查询的指标，并提供 YYYY-MM-DD 报告日。"
            )
        cards = [
            AgentCard(
                type="metric_candidate",
                title=reference.name,
                data={"entity_id": reference.entity_id},
                metric_id=reference.entity_id,
            )
            for reference in references
        ]
        return self._semantic_no_data_envelope(
            request=request,
            resolution=resolution,
            answer=answer,
            cards=cards,
            result_kind="agent.ontology_clarification",
            result_check="blocked",
            references=references,
        )

    def _semantic_unsupported_envelope(
        self,
        request: AgentQueryRequest,
        resolution: LocalRequestResolution,
    ) -> AgentEnvelope:
        references = self._semantic_references(resolution)
        if resolution.semantic_reason_code == "unsupported_query_scope":
            answer = (
                "当前正式损益 Ontology 能力只支持 overview 的全量单报告日读取，"
                "尚不支持组合、币种、账户筛选，或剔除、扣除部分对象。"
                "本次未调用正式取数，请明确是否查询全量范围。"
            )
        elif resolution.semantic_reason_code == "unsupported_period_query":
            answer = (
                "当前能力只支持单个报告日的指标数值，不支持最近若干天、月初至今等期间查询。"
                "本次未调用正式取数，请明确一个 YYYY-MM-DD 报告日，并移除期间条件。"
            )
        elif resolution.semantic_reason_code == "unsupported_derived_operation":
            answer = (
                "当前能力只支持指标原值，尚不支持占比、比例、平均值等派生计算。"
                "本次未调用正式取数；如需原值，请指定指标和一个 YYYY-MM-DD 报告日。"
            )
        elif resolution.semantic_reason_code == "unsupported_metric":
            answer = (
                "首期正式损益 Ontology 尚未纳入 517 资本利得指标。"
                "本次未调用正式取数，请改查已支持的 514 利息收入、516 公允价值变动或正式总损益。"
            )
        else:
            answer = (
                "当前能力支持指标定义和单个报告日数值查询；期间比较、趋势或原因归因"
                "需要明确比较期间及对应的受治理分析能力。"
            )
        return self._semantic_no_data_envelope(
            request=request,
            resolution=resolution,
            answer=answer,
            cards=[],
            result_kind="agent.ontology_unsupported",
            result_check="blocked",
            references=references,
        )

    def _semantic_unavailable_envelope(
        self,
        request: AgentQueryRequest,
        resolution: LocalRequestResolution,
    ) -> AgentEnvelope:
        unavailable_resolution = LocalRequestResolution(
            route="local",
            reason="ontology_unavailable",
            intent="ontology_unavailable",
            semantic_status="unavailable",
            metric_id=resolution.metric_id,
            metric_candidates=resolution.metric_candidates,
            semantic_reason_code=(
                resolution.semantic_reason_code or "ontology_unavailable"
            ),
        )
        return self._semantic_no_data_envelope(
            request=request,
            resolution=unavailable_resolution,
            answer="指标语义或已核对绑定当前不可用，系统未执行正式损益取数。",
            cards=[],
            result_kind="agent.ontology_unavailable",
            result_check="blocked",
            references=[],
        )

    def _semantic_no_data_envelope(
        self,
        *,
        request: AgentQueryRequest,
        resolution: LocalRequestResolution,
        answer: str,
        cards: list[AgentCard],
        result_kind: str,
        result_check: Literal["blocked", "not_applicable"],
        references: list[AgentSemanticReference],
    ) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="warning",
        )
        result_meta = self._result_meta(
            request=request,
            result_kind=result_kind,
            formal_use_allowed=False,
            source_version=self._semantic_ontology_revision() or "sv_ontology_unavailable",
            rule_version=ONTOLOGY_BINDING_REVISION,
            cache_version="cv_agent_ontology_v1",
            quality_flag="warning",
            evidence=evidence,
            requested_report_date=resolution.report_date,
            resolved_report_date=None,
            scenario_flag=False,
            tables_used=[],
            filters_applied={},
            sql_executed=[],
            evidence_rows=0,
            next_drill=[],
        )
        semantic_context = AgentSemanticContext(
            status=resolution.semantic_status or "unavailable",
            result_check=result_check,
            references=references,
            ontology_revision=self._semantic_ontology_revision(),
            binding_revision=ONTOLOGY_BINDING_REVISION,
            reason_code=resolution.semantic_reason_code,
        )
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=answer,
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
                semantic_context=semantic_context,
            )
        )

    def _semantic_references(
        self,
        resolution: LocalRequestResolution,
    ) -> list[AgentSemanticReference]:
        metric_ids = resolution.metric_candidates
        if not metric_ids and resolution.metric_id:
            metric_ids = (resolution.metric_id,)
        references: list[AgentSemanticReference] = []
        for metric_id in metric_ids:
            try:
                references.append(
                    AgentSemanticReference.model_validate(
                        ontology_reference_payload(metric_id)
                    )
                )
            except (KeyError, OSError, TypeError, ValueError):
                continue
        return references

    @staticmethod
    def _semantic_ontology_revision() -> str | None:
        try:
            return ontology_content_revision()
        except (OSError, TypeError, ValueError):
            return None

    def _unknown_workflow_envelope(self, request: AgentQueryRequest) -> AgentEnvelope:
        """显式传入的 workflow_id 未命中目录：返回错误 envelope，不静默降级到问题扫描。"""
        requested_workflow_id = str(request.context.get("workflow_id") or "").strip()
        known_workflow_ids = [
            workflow.workflow_id for workflow in list_financial_workflows()
        ] + [workflow.workflow_id for workflow in list_research_workflows()]
        return self._error_envelope(
            request=request,
            intent="unknown_workflow",
            detail=(
                f"Unrecognized workflow_id '{requested_workflow_id}'. "
                f"Known workflows: {', '.join(known_workflow_ids)}."
            ),
        )

    @staticmethod
    def _workflow_mode_violation(workflow_mode: str) -> str | None:
        """workflow_mode 仅接受空值 / plan / execute；其他值不再静默按 plan 处理。"""
        if workflow_mode in ("", "plan", "execute"):
            return None
        return (
            f"Unsupported workflow_mode '{workflow_mode}'; "
            "expected 'plan' or 'execute'."
        )

    def _workflow_envelope(
        self,
        request: AgentQueryRequest,
        workflow: FinancialWorkflow,
    ) -> AgentEnvelope:
        requested_report_date = _requested_report_date(request)
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="warning",
        )
        next_intent = workflow.mapped_intents[0] if workflow.mapped_intents else ""
        result_meta = self._result_meta(
            request=request,
            result_kind=f"agent.workflow.{workflow.workflow_id}",
            formal_use_allowed=False,
            source_version="sv_anthropic_financial_workflow_reference",
            rule_version="rv_agent_financial_workflow_catalog_v1",
            cache_version=f"cv_agent_workflow_{workflow.workflow_id}_v1",
            quality_flag="warning",
            evidence=evidence,
            requested_report_date=requested_report_date,
            resolved_report_date=None,
            scenario_flag=request.basis == "scenario",
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
            # payload 契约：仅携带 intent。回传 context 时走 explicit intent 路径直接执行
            # 第一个 mapped intent；不携带 workflow_id，避免回传后再次命中 workflow 解析
            # 而返回 plan 卡（与动作标签 "Execute first mapped intent" 语义一致）。
            payload = {"intent": next_intent}
            suggested_actions.append(
                self._suggested_action(
                    action_type="execute_intent",
                    label=f"Execute first mapped intent: {next_intent}",
                    payload=payload,
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
        sql_executed: list[str] = []
        evidence_rows = 0
        failed_intents: list[str] = []
        degraded_intents: list[str] = []
        requested_report_date = _requested_report_date(request)
        workflow_pinned_report_date: str | None = requested_report_date
        successful_resolved_report_dates: list[str] = []
        successful_child_count = 0

        for index, intent in enumerate(workflow.mapped_intents, start=1):
            step_request = (
                _request_with_report_date(request, workflow_pinned_report_date)
                if workflow_pinned_report_date is not None
                else request
            )
            step_requested_report_date = _requested_report_date(step_request)
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
                        "requested_report_date": step_requested_report_date,
                        "resolved_report_date": None,
                    }
                )
                continue

            try:
                envelope = self._payload_envelope(
                    request=step_request,
                    intent=intent,
                    payload=handler(step_request),
                )
            except Exception as exc:  # noqa: BLE001 - Record failed workflow children while preserving independent read-only steps.
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
                        "message": _safe_execution_error_detail(exc),
                        "requested_report_date": step_requested_report_date,
                        "resolved_report_date": None,
                    }
                )
                continue

            child_requested_report_date = (
                envelope.result_meta.requested_report_date or step_requested_report_date
            )
            child_resolved_report_date = (
                envelope.result_meta.resolved_report_date
                or _optional_text(envelope.evidence.filters_applied.get("report_date"))
            )
            successful_child_count += 1
            if child_resolved_report_date is not None:
                successful_resolved_report_dates.append(child_resolved_report_date)
                if requested_report_date is None and workflow_pinned_report_date is None:
                    workflow_pinned_report_date = child_resolved_report_date
                    filters_applied["workflow_pinned_report_date"] = child_resolved_report_date

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
                    "requested_report_date": child_requested_report_date,
                    "resolved_report_date": child_resolved_report_date,
                }
            )
            evidence_rows += envelope.evidence.evidence_rows
            for table in envelope.evidence.tables_used:
                if table not in tables_used:
                    tables_used.append(table)
            for statement in envelope.evidence.sql_executed:
                if statement not in sql_executed:
                    sql_executed.append(statement)
            for key, value in envelope.evidence.filters_applied.items():
                filters_applied[f"{intent}.{key}"] = value
            if envelope.result_meta.quality_flag != "ok":
                degraded_intents.append(intent)

        # 全部步骤硬失败（missing/error，无任何 status=ok 的结果）时整体与
        # 步骤 quality_flag 升为 error，避免「全失败仍 warning」的矛盾展示；
        # 部分失败保持既有 warning 语义。
        all_steps_failed = bool(workflow.mapped_intents) and not any(
            row.get("status") == "ok" for row in step_rows
        )
        if all_steps_failed:
            for row in step_rows:
                row["quality_flag"] = "error"
        quality_flag: Literal["ok", "warning", "error", "stale"] = (
            "error" if all_steps_failed else "warning" if failed_intents or degraded_intents else "ok"
        )
        unique_resolved_report_dates = list(
            dict.fromkeys(successful_resolved_report_dates)
        )
        resolved_report_date = (
            unique_resolved_report_dates[0]
            if successful_child_count > 0
            and successful_child_count == len(workflow.mapped_intents)
            and len(successful_resolved_report_dates) == successful_child_count
            and len(unique_resolved_report_dates) == 1
            else None
        )
        if failed_intents:
            filters_applied["workflow_failed_intents"] = list(failed_intents)
        if degraded_intents:
            filters_applied["workflow_degraded_intents"] = list(degraded_intents)
        evidence = self._evidence.build_evidence(
            tables_used=tables_used,
            filters_applied=filters_applied,
            row_count=evidence_rows,
            quality_flag=quality_flag,
            sql_executed=sql_executed,
        )
        result_meta = self._result_meta(
            request=request,
            result_kind=f"agent.workflow.{workflow.workflow_id}",
            formal_use_allowed=False,
            source_version="sv_anthropic_financial_workflow_reference",
            rule_version="rv_agent_financial_workflow_catalog_v1",
            cache_version=f"cv_agent_workflow_{workflow.workflow_id}_v1",
            quality_flag=quality_flag,
            evidence=evidence,
            requested_report_date=requested_report_date,
            resolved_report_date=resolved_report_date,
            scenario_flag=request.basis == "scenario",
            next_drill=[],
        )
        cards = [
            self._workflow_memo_card(
                workflow_title=workflow.title,
                workflow_id=workflow.workflow_id,
                step_rows=step_rows,
                detail_rows=detail_rows,
            ),
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

        if all_steps_failed:
            answer = (
                f"Failed to execute financial workflow '{workflow.title}' ({workflow.workflow_id}): "
                f"all mapped intents failed ({', '.join(failed_intents)}). "
                "No governed intent produced a result. "
                "The workflow summary is not a formal financial result."
            )
        elif failed_intents:
            answer = (
                f"Executed financial workflow '{workflow.title}' ({workflow.workflow_id}) with warnings. "
                f"Failed intents: {', '.join(failed_intents)}. "
                + (
                    f"Degraded intents: {', '.join(degraded_intents)}. "
                    if degraded_intents
                    else ""
                )
                + "The workflow summary is not a formal financial result."
            )
        elif degraded_intents:
            answer = (
                f"Executed financial workflow '{workflow.title}' ({workflow.workflow_id}) with data quality warnings. "
                f"Degraded intents: {', '.join(degraded_intents)}. "
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

    def _execute_research_workflow(
        self,
        request: AgentQueryRequest,
        workflow: ResearchWorkflow,
    ) -> AgentEnvelope:
        handler = self._intent_handlers.get(workflow.workflow_id)
        if handler is None:
            return self._error_envelope(
                request=request,
                intent=workflow.workflow_id,
                detail="No registered research workflow handler.",
            )
        try:
            return self._payload_envelope(
                request=request,
                intent=workflow.workflow_id,
                payload=handler(request),
            )
        except Exception as exc:  # noqa: BLE001 - Research handlers must emit a non-formal error envelope on any execution failure.
            return self._error_envelope(
                request=request,
                intent=workflow.workflow_id,
                detail=_safe_execution_error_detail(exc),
            )

    def _research_workflow_plan_envelope(
        self,
        request: AgentQueryRequest,
        workflow: ResearchWorkflow,
    ) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="warning",
        )
        result_meta = self._result_meta(
            request=request,
            result_kind=f"agent.workflow.{workflow.workflow_id}",
            formal_use_allowed=False,
            source_version=workflow.source_version,
            rule_version=workflow.rule_version,
            cache_version=workflow.cache_version,
            quality_flag="warning",
            evidence=evidence,
            scenario_flag=request.basis == "scenario",
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
                    "source": "moss_research_workflow_catalog",
                    "output_kind": workflow.result_kind,
                    "phase": "plan_only",
                },
            ),
            AgentCard(
                type="workflow_intents",
                title="Mapped MOSS Intents",
                data=[{"order": 1, "intent": workflow.workflow_id}],
            ),
            AgentCard(
                type="governance_notes",
                title="Governance Notes",
                data=[{"note": note} for note in workflow.governance_notes],
            ),
        ]
        suggested_actions = [
            self._suggested_action(
                action_type="execute_intent",
                label=f"Execute research workflow: {workflow.workflow_id}",
                payload={
                    "intent": workflow.workflow_id,
                    "workflow_id": workflow.workflow_id,
                    "workflow_mode": "execute",
                },
                requires_confirmation=True,
            )
        ]
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=(
                    f"Identified research workflow '{workflow.title}' ({workflow.workflow_id}). "
                    "This response is a workflow plan only, not a formal financial result. "
                    "Set context.workflow_mode=\"execute\" (or use the suggested action) to run the governed "
                    f"research intent: {workflow.workflow_id}."
                ),
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
                suggested_actions=suggested_actions,
            )
        )

    def _workflow_memo_card(
        self,
        *,
        workflow_title: str,
        workflow_id: str,
        step_rows: list[dict[str, Any]],
        detail_rows: list[dict[str, Any]],
    ) -> AgentCard:
        """纯模板化 memo 合成（不调用 LLM）：仅重排既有子 envelope 结论，不新增取数或计算。"""
        # 使用已按 child result_meta -> evidence fallback 解析后的结构化日期，
        # 避免 memo 与顶层 / child result_meta 展示不同的日期。
        report_dates_by_intent: dict[str, str] = {}
        for row in detail_rows:
            if row.get("status") != "ok":
                continue
            intent = _optional_text(row.get("intent"))
            resolved_report_date = _optional_text(row.get("resolved_report_date"))
            if intent is not None and resolved_report_date is not None:
                report_dates_by_intent[intent] = resolved_report_date
        unique_report_dates = list(dict.fromkeys(report_dates_by_intent.values()))
        if not unique_report_dates:
            report_date_line = "报告日期：未提供"
        elif len(unique_report_dates) == 1:
            report_date_line = f"报告日期：{unique_report_dates[0]}"
        else:
            per_intent_dates = "；".join(
                f"{intent}={value}" for intent, value in report_dates_by_intent.items()
            )
            report_date_line = f"报告日期：子意图日期不一致（{per_intent_dates}）"
        conclusion_lines: list[str] = []
        for row in detail_rows:
            intent = str(row.get("intent") or "")
            if row.get("status") == "ok":
                first_sentence = str(row.get("answer") or "").strip().splitlines()[0] if str(row.get("answer") or "").strip() else "已返回结果。"
                conclusion_lines.append(f"- {intent}: {first_sentence}")
            else:
                conclusion_lines.append(
                    f"- {intent}: 执行失败（{row.get('status')}）：{row.get('message', '')}"
                )
        quality_lines = [
            f"- {row['intent']}: quality_flag={row['quality_flag']}（status={row['status']}）"
            for row in step_rows
            if str(row.get("quality_flag")) != "ok" or str(row.get("status")) != "ok"
        ]
        sections = [
            f"## Workflow Memo：{workflow_title}（{workflow_id}）",
            report_date_line,
            "",
            "### 分步结论",
            *conclusion_lines,
        ]
        if quality_lines:
            sections.extend(["", "### 数据质量提示", *quality_lines])
        sections.extend(["", "非正式结果，仅供分析参考（formal_use_allowed=false）。"])
        return AgentCard(
            type="markdown",
            title="Workflow Memo",
            value="\n".join(sections),
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
        filters_applied: dict[str, Any] = {
            path.dimension: path.current_filter
            for path in cube_response.drill_paths
            if path.current_filter
        }
        # WHERE 恒含 report_date（cube_query_service.build_where_clause），一并披露
        # 请求锚点，避免 cube 路径成为零披露的动态 SQL 执行面。
        filters_applied["report_date"] = cube_response.report_date
        filters_applied["fact_table"] = cube_response.fact_table
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
            sql_executed=self._cube_query_sql_disclosure(cube_request, table_name),
        )
        cube_meta = cube_response.result_meta.model_dump(mode="python")
        result_meta = self._result_meta(
            request=request,
            trace_id=str(cube_meta["trace_id"]),
            basis=cast(Literal["formal", "scenario", "analytical", "ledger"], cube_meta["basis"]),
            result_kind=str(cube_meta["result_kind"]),
            formal_use_allowed=bool(cube_meta["formal_use_allowed"]),
            amount_currency_basis=_optional_text(cube_meta.get("amount_currency_basis")),
            amount_currency_basis_note=_optional_text(cube_meta.get("amount_currency_basis_note")),
            source_version=str(cube_meta["source_version"]),
            vendor_version=str(cube_meta.get("vendor_version") or "vv_none"),
            rule_version=str(cube_meta["rule_version"]),
            cache_version=str(cube_meta["cache_version"]),
            cache_key=_optional_text(cube_meta.get("cache_key")),
            quality_flag=cast(Literal["ok", "warning", "error", "stale"], cube_meta["quality_flag"]),
            vendor_status=cast(
                Literal["ok", "vendor_stale", "vendor_unavailable"],
                cube_meta.get("vendor_status") or "ok",
            ),
            fallback_mode=cast(Literal["none", "latest_snapshot"], cube_meta.get("fallback_mode") or "none"),
            requested_report_date=_optional_text(cube_meta.get("requested_report_date")),
            resolved_report_date=_optional_text(cube_meta.get("resolved_report_date")),
            scenario_flag=bool(cube_meta.get("scenario_flag", False)),
            as_of_date=_optional_text(cube_meta.get("as_of_date")),
            date_basis=_optional_text(cube_meta.get("date_basis")),
            fallback_date=_optional_text(cube_meta.get("fallback_date")),
            evidence=evidence,
            next_drill=next_drill,
            source_surface=cast(SourceSurface | None, _optional_text(cube_meta.get("source_surface"))),
            generated_at=cube_meta.get("generated_at"),
            data_built_at=cube_meta.get("data_built_at"),
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

    def _cube_query_sql_disclosure(
        self,
        cube_request: CubeQueryRequest,
        table_name: str,
    ) -> list[str]:
        """仅用于披露（sql_executed）：与 CubeQueryService 执行链路同源的只读
        参数化模板。where 由 build_where_clause 生成（恒含 report_date = ?，
        过滤值全部保持 `?` 绑定占位），维度/度量/表名均已过服务端白名单校验；
        实际绑定值见 evidence.filters_applied。此处从不执行任何语句。"""
        filters = self._cube_query_service.validate_filters(cube_request)
        where_sql, _params = self._cube_query_service.build_where_clause(
            cube_request.report_date,
            filters,
        )
        dimensions = self._cube_query_service.validate_dimensions(cube_request)
        measure_specs = self._cube_query_service.parse_measures(cube_request)
        select_parts = list(dimensions) + [
            f"{spec.sql} as {spec.alias}" for spec in measure_specs
        ]
        group_sql = f" group by {', '.join(dimensions)}" if dimensions else ""
        return [
            f"select count(*) from {table_name}{where_sql}",
            (
                f"select {', '.join(select_parts)} from {table_name}"
                f"{where_sql}{group_sql} limit ? offset ?"
            ),
        ]

    def _analysis_chat_envelope(self, request: AgentQueryRequest) -> AgentEnvelope:
        filters_applied = self._analysis_chat_filters(request)
        is_chinese = self._is_chinese_text(request.question)
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied=filters_applied,
            row_count=0,
            quality_flag="warning",
        )
        result_meta = self._result_meta(
            request=request,
            result_kind="agent.analysis_chat",
            formal_use_allowed=False,
            source_version="sv_agent_local_analysis_chat",
            rule_version="rv_agent_local_analysis_chat_v1",
            cache_version="cv_agent_local_analysis_chat_v1",
            quality_flag="warning",
            evidence=evidence,
            scenario_flag=request.basis == "scenario",
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
            self._suggested_action(
                action_type="execute_intent",
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
            sql_executed=list(payload.get("sql_executed", [])),
        )
        result_meta = self._result_meta(
            request=request,
            trace_id=str(payload.get("trace_id") or self._trace_id(f"agent.{intent}")),
            basis=cast(Literal["formal", "scenario", "analytical", "ledger"], payload.get("basis") or request.basis),
            result_kind=str(payload.get("result_kind") or f"agent.{intent}"),
            formal_use_allowed=bool(payload.get("formal_use_allowed", False)),
            amount_currency_basis=_optional_text(payload.get("amount_currency_basis")),
            amount_currency_basis_note=_optional_text(payload.get("amount_currency_basis_note")),
            source_version=str(payload.get("source_version") or "sv_agent_unknown"),
            vendor_version=str(payload.get("vendor_version") or "vv_none"),
            rule_version=str(payload.get("rule_version") or "rv_agent_mvp_v1"),
            cache_version=str(payload.get("cache_version") or f"cv_agent_{intent}_v1"),
            cache_key=_optional_text(payload.get("cache_key")),
            quality_flag=cast(Literal["ok", "warning", "error", "stale"], payload.get("quality_flag") or "warning"),
            vendor_status=cast(
                Literal["ok", "vendor_stale", "vendor_unavailable"],
                payload.get("vendor_status") or "ok",
            ),
            fallback_mode=cast(Literal["none", "latest_snapshot"], payload.get("fallback_mode") or "none"),
            requested_report_date=_optional_text(payload.get("requested_report_date")),
            resolved_report_date=_optional_text(payload.get("resolved_report_date")),
            scenario_flag=bool(payload.get("scenario_flag", False)),
            as_of_date=_optional_text(payload.get("as_of_date")),
            date_basis=_optional_text(payload.get("date_basis")),
            fallback_date=_optional_text(payload.get("fallback_date")),
            evidence=evidence,
            next_drill=next_drill,
            source_surface=cast(SourceSurface | None, _optional_text(payload.get("source_surface"))),
            generated_at=payload.get("generated_at"),
            data_built_at=payload.get("data_built_at"),
        )
        semantic_context_payload = payload.get("semantic_context")
        semantic_context = (
            semantic_context_payload
            if isinstance(semantic_context_payload, AgentSemanticContext)
            else AgentSemanticContext.model_validate(semantic_context_payload)
            if isinstance(semantic_context_payload, dict)
            else None
        )
        answer_mode = str(payload.get("answer_mode") or "business").strip().lower()
        raw_answer = str(payload.get("answer") or "")
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=(
                    raw_answer
                    if answer_mode == "raw"
                    else self._business_answer(
                        conclusion=raw_answer,
                        cards=cards,
                        evidence=evidence,
                        result_meta=result_meta,
                        next_drill=next_drill,
                    )
                ),
                cards=cards,
                evidence=evidence,
                result_meta=result_meta,
                next_drill=next_drill,
                suggested_actions=suggested_actions,
                semantic_context=semantic_context,
            )
        )

    def _unsupported_envelope(self, request: AgentQueryRequest) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={},
            row_count=0,
            quality_flag="warning",
        )
        result_meta = self._result_meta(
            request=request,
            result_kind="agent.unknown",
            formal_use_allowed=False,
            source_version="sv_agent_unknown",
            rule_version="rv_agent_mvp_v1",
            cache_version="cv_agent_unknown_v1",
            quality_flag="warning",
            evidence=evidence,
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
        semantic_reason_code: str | None = None,
    ) -> AgentEnvelope:
        evidence = self._evidence.build_evidence(
            tables_used=[],
            filters_applied={key: value for key, value in request.filters.items() if value not in (None, "")},
            row_count=0,
            quality_flag="error",
        )
        result_meta = self._result_meta(
            request=request,
            result_kind=f"agent.{intent}",
            formal_use_allowed=False,
            source_version="sv_agent_error",
            rule_version="rv_agent_mvp_v1",
            cache_version=f"cv_agent_{intent}_v1",
            quality_flag="error",
            evidence=evidence,
            scenario_flag=False,
            tables_used=[],
            filters_applied=evidence.filters_applied,
            sql_executed=[],
            evidence_rows=0,
            next_drill=[],
        )
        semantic_context: AgentSemanticContext | None = None
        try:
            resolution = resolve_local_request(request)
            if resolution.semantic_status is not None:
                semantic_context = AgentSemanticContext(
                    status=resolution.semantic_status,
                    result_check="blocked",
                    references=self._semantic_references(resolution),
                    ontology_revision=self._semantic_ontology_revision(),
                    binding_revision=ONTOLOGY_BINDING_REVISION,
                    reason_code=semantic_reason_code or "metric_execution_failed",
                )
        except (TypeError, ValueError):
            semantic_context = None
        return AgentEnvelope(
            **self._finalize_envelope(
                answer=f"{intent} 查询失败：{detail}",
                cards=[AgentCard(type="status", title="Error", value=detail)],
                evidence=evidence,
                result_meta=result_meta,
                next_drill=[],
                semantic_context=semantic_context,
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
                self._ensure_action_confirmation_token(
                    action if isinstance(action, AgentSuggestedAction) else AgentSuggestedAction.model_validate(action)
                )
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
            self._suggested_action(
                action_type="inspect_drill",
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

    def _suggested_action(
        self,
        *,
        action_type: str,
        label: str,
        payload: dict[str, Any],
        requires_confirmation: bool,
    ) -> AgentSuggestedAction:
        return self._ensure_action_confirmation_token(
            AgentSuggestedAction(
                type=action_type,
                label=label,
                payload=payload,
                requires_confirmation=requires_confirmation,
            )
        )

    def _confirmation_scope(self, request: AgentQueryRequest) -> dict[str, str] | None:
        """从服务端注入的 context 提取 token 作用域（客户端提交的 run_id 已在 API 层剥离）。"""
        scope: dict[str, str] = {}
        user_id = str(request.context.get("user_id") or "").strip()
        if user_id:
            scope["user_id"] = user_id
        run_id = str(request.context.get("run_id") or "").strip()
        if run_id:
            scope["run_id"] = run_id
        return scope or None

    def _suggested_action_scope_violation(self, request: AgentQueryRequest) -> str | None:
        """user 维度强制校验；run_id 仅随 scope 记录供审计追溯（确认发生在新请求/新 run 中）。

        scope 位于 action payload 内，受既有确认 token HMAC 保护，客户端无法篡改。
        无 scope 的确认类动作已在签发侧拒发、在路由 token 校验点拒绝（fail-closed）；
        本层对无 scope 上下文保持透传，仅覆盖非确认类动作回显。
        """
        action = request.context.get("suggested_action")
        if not isinstance(action, dict):
            return None
        payload = action.get("payload")
        if not isinstance(payload, dict):
            return None
        scope = payload.get("confirmation_scope")
        if not isinstance(scope, dict):
            return None
        issued_user = str(scope.get("user_id") or "").strip()
        if not issued_user:
            return None
        current_user = str(request.context.get("user_id") or "").strip()
        if issued_user == current_user:
            return None
        return (
            "Suggested action confirmation is bound to user scope "
            f"'{issued_user}' and cannot be executed as '{current_user or 'unknown'}'."
        )

    def _ensure_action_confirmation_token(self, action: AgentSuggestedAction) -> AgentSuggestedAction:
        if not action.requires_confirmation or action.confirmation_token:
            return action
        payload = dict(action.payload)
        if self._action_scope and "confirmation_scope" not in payload:
            payload["confirmation_scope"] = dict(self._action_scope)
        # 签发 fail-closed：payload 仍缺 confirmation_scope.user_id 时（请求
        # 上下文没有 user_id），agent_action_confirmation_token 会拒绝签发并抛错，
        # 防止产生可被任意用户重放的未绑定 token。
        return action.model_copy(
            update={
                "payload": payload,
                "confirmation_token": self._confirmation_token_for_action(
                    action_type=action.type,
                    label=action.label,
                    payload=payload,
                ),
            }
        )

    def _confirmation_token_for_action(
        self,
        *,
        action_type: str,
        label: str,
        payload: dict[str, Any],
    ) -> str:
        return agent_action_confirmation_token(
            action_type=action_type,
            label=label,
            payload=payload,
        )

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
        semantic_context: AgentSemanticContext | None = None,
    ) -> dict[str, Any]:
        result_meta = result_meta.model_copy(
            update={
                "evidence_strength": evidence.evidence_strength,
                "quality_flag": evidence.quality_flag,
            }
        )
        return {
            "answer": answer,
            "cards": [card.model_dump(mode="python") for card in cards],
            "evidence": evidence.model_dump(mode="python"),
            "result_meta": result_meta.model_dump(mode="python"),
            "next_drill": [drill.model_dump(mode="python") for drill in next_drill],
            "suggested_actions": [
                action.model_dump(mode="python") for action in (suggested_actions or [])
            ],
            "semantic_context": (
                semantic_context.model_dump(mode="python")
                if semantic_context is not None
                else None
            ),
        }
