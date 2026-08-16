from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from backend.app.agent.runtime.financial_workflow_catalog import (
    FinancialWorkflow,
    get_financial_workflow,
    is_financial_workflow_id,
    resolve_financial_workflow,
)
from backend.app.agent.runtime.research_workflow_catalog import (
    ResearchWorkflow,
    get_research_workflow,
    is_research_workflow_id,
    list_research_workflows,
    resolve_research_workflow,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest

_INTENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    # 「影响分析」是金融/代码双关词，不入主关键词表；只有与 code/repo/仓库 等
    # 域词同现时才路由 gitnexus（见 _GITNEXUS_AMBIGUOUS_TERMS 守卫）。
    (
        "gitnexus_status",
        ("gitnexus", "仓库图谱", "代码图谱", "repo graph", "code graph"),
    ),
    # 两个观察面意图放在宽泛金融词表之前：「盘前…损益」「策略样本外…收益」等
    # 问法应命中更具体的盘前清单 / walk-forward 判定，而不是被 pnl_summary、
    # market_data 等通用词表截走。
    (
        "pretrade_checklist",
        (
            "盘前",
            "操作清单",
            "开盘检查",
            "开盘清单",
            "开盘checklist",
            "开盘 checklist",
            "买什么",
            "可以买",
            "可买",
            "pretrade",
            "pre-trade",
        ),
    ),
    (
        "walk_forward_verdict",
        (
            "样本外",
            "样本内外",
            "walk-forward",
            "walk forward",
            "walkforward",
            "策略靠谱",
            "回测验证",
            "策略回测",
            "策略验证",
            "out-of-sample",
            "out of sample",
        ),
    ),
    ("product_pnl", ("产品损益", "ftp")),
    ("pnl_bridge", ("桥接", "归因", "拆解", "bridge", "attribution")),
    ("risk_tensor", ("风险张量", "krd")),
    ("duration_risk", ("久期", "dv01", "利率风险")),
    ("credit_exposure", ("信用", "利差", "集中度", "credit", "spread", "concentration")),
    (
        "portfolio_overview",
        ("组合概览", "资产规模", "总览", "portfolio overview", "portfolio value", "asset size"),
    ),
    # 中文歧义词守卫：裸词「收益」不入表，避免「收益率」（曲线/市场问法）误路由到
    # pnl_summary；非「收益率」的「收益」问法由 _CHINESE_PNL_RETURN_PATTERN 在同一
    # 优先级位置兜住（见 _intent_from_question）。
    ("pnl_summary", ("损益", "pnl")),
    ("market_data", ("宏观", "利率", "收益率", "市场数据", "macro", "market data", "macro data", "rates data")),
    ("news", ("新闻", "事件", "news", "headline", "latest news")),
]

_PAGE_DEFAULT_INTENTS = {
    "dashboard": "portfolio_overview",
    "bond-dashboard": "portfolio_overview",
    "balance-analysis": "portfolio_overview",
    "pnl-attribution": "pnl_bridge",
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
    "分析",
    "解释",
    "总结",
    "判断",
    "风险",
    "结论",
    "说明",
    "继续",
    "追问",
)

_FOLLOW_UP_PATTERNS = (
    "continue",
    "follow up",
    "follow-up",
    "what about this",
    "how about this",
    "what about that",
    "and this",
    "and that",
    "continue this",
    "continue that",
    "drill into this",
    "继续",
    "追问",
    "再看",
    "这个",
    "这项",
    "那个",
)

_PAGE_CONTEXT_PATTERNS = (
    "当前页",
    "当前页面",
    "这个页面",
    "本页",
    "页面",
    "current page",
    "this page",
)

_EXTERNAL_PROVIDER_PATTERNS = (
    "external provider",
    "provider health",
    "provider diagnostic",
    "provider diagnostics",
    "hermes health",
    "dexter health",
    "hermes diagnostic",
    "dexter diagnostic",
)

_GITNEXUS_AMBIGUOUS_TERMS = ("context", "process", "processes", "影响分析")
_GITNEXUS_DOMAIN_TERMS = (
    "gitnexus",
    "code",
    "repo",
    "repository",
    "symbol",
    "call graph",
    "仓库",
    "代码",
)
_DURATION_DOMAIN_TERMS = (
    "asset",
    "bond",
    "effective",
    "fixed income",
    "interest rate",
    "liability",
    "modified",
    "portfolio",
    "rate risk",
    "risk",
)
# 「收益」仅在不是「收益率」的一部分时才算 PnL 语义（如「今日收益」「投资收益」）。
_CHINESE_PNL_RETURN_PATTERN = re.compile(r"收益(?!率)")
_MARKET_VALUE_DOMAIN_TERMS = (
    "account",
    "asset",
    "balance sheet",
    "bond",
    "fund",
    "holding",
    "portfolio",
    "position",
)

_LOCAL_INTENTS = frozenset(intent for intent, _keywords in _INTENT_PATTERNS)


@dataclass(frozen=True)
class LocalRequestResolution:
    route: Literal["local", "provider"]
    reason: str
    intent: str | None = None
    financial_workflow: FinancialWorkflow | None = None
    research_workflow: ResearchWorkflow | None = None


def is_explicit_local_agent_intent(intent: str) -> bool:
    normalized = _normalize_intent(intent)
    return normalized in _LOCAL_INTENTS or is_research_workflow_id(normalized)


def has_explicit_local_agent_context(context: dict[str, Any] | None) -> bool:
    context = context or {}
    explicit_intent = _normalize_intent(context.get("intent"))
    explicit_workflow = _normalize_intent(context.get("workflow_id"))
    return (
        explicit_intent == "cube_query"
        or is_explicit_local_agent_intent(explicit_intent)
        or is_financial_workflow_id(explicit_workflow)
        or is_research_workflow_id(explicit_workflow)
    )


def is_plain_analysis_chat_question(question: str) -> bool:
    normalized = _normalize_text(question)
    if not normalized:
        return False
    if not any(
        _matches_analysis_pattern(normalized, pattern)
        for pattern in _ANALYSIS_CHAT_PATTERNS
    ):
        return False
    return _intent_from_question(normalized) is None


def resolve_local_request(request: AgentQueryRequest) -> LocalRequestResolution:
    normalized_question = _normalize_text(request.question)
    if _is_explicit_external_provider_prompt(normalized_question):
        return LocalRequestResolution(
            route="provider",
            reason="provider_diagnostic",
        )

    # 显式 context.workflow_id 是最强声明：命中目录即路由对应工作流；
    # 未命中时 fail-closed 走本地错误提示，不再静默降级到问题级扫描
    # （避免拼错的 workflow_id 被送去 provider 开放聊天）。
    explicit_workflow_id = str(request.context.get("workflow_id") or "").strip()
    if explicit_workflow_id:
        explicit_financial = get_financial_workflow(explicit_workflow_id)
        if explicit_financial is not None:
            return LocalRequestResolution(
                route="local",
                reason="financial_workflow",
                financial_workflow=explicit_financial,
            )
        explicit_research = get_research_workflow(explicit_workflow_id)
        if explicit_research is not None:
            return LocalRequestResolution(
                route="local",
                reason="research_workflow",
                research_workflow=explicit_research,
            )
        return LocalRequestResolution(
            route="local",
            reason="unknown_workflow",
            intent="unknown_workflow",
        )

    # 显式 context.intent / cube_query 优先于问题级 slash/关键词工作流解析：
    # plan 卡的建议动作 payload 只携带 intent，调用方按文档 merge 回传时可能
    # 沿用原 slash 问题；此时应直接执行 intent，而不是再次返回 plan 卡形成回环。
    explicit_intent = _normalize_intent(request.context.get("intent"))
    if explicit_intent == "cube_query" or "cube_query" in request.context:
        return LocalRequestResolution(
            route="local",
            reason="explicit_cube_query",
            intent="cube_query",
        )
    if explicit_intent and is_explicit_local_agent_intent(explicit_intent):
        return LocalRequestResolution(
            route="local",
            reason="explicit_intent",
            intent=explicit_intent,
        )

    financial_workflow = resolve_financial_workflow(request.question, None)
    if financial_workflow is not None:
        return LocalRequestResolution(
            route="local",
            reason="financial_workflow",
            financial_workflow=financial_workflow,
        )

    research_workflow = resolve_research_workflow(request.question, None)
    if research_workflow is not None:
        return LocalRequestResolution(
            route="local",
            reason="research_workflow",
            research_workflow=research_workflow,
        )

    keyword_intent = _intent_from_question(normalized_question, request=request)
    if keyword_intent is not None:
        return LocalRequestResolution(
            route="local",
            reason="governed_keyword",
            intent=keyword_intent,
        )

    # 页面上下文问句（「这个页面 / 当前页」）先于 follow-up 判定：
    # 「这个」等裸指代词同时也是 follow-up 标记，若 follow-up 先行会复用
    # 上一轮意图，导致 page_default 分支不可达。
    if _is_page_context_question(normalized_question):
        page_intent = _page_default_intent(request)
        if page_intent is not None:
            return LocalRequestResolution(
                route="local",
                reason="page_default",
                intent=page_intent,
            )

    follow_up_intent = _conversation_intent(request, normalized_question)
    if follow_up_intent is not None:
        return LocalRequestResolution(
            route="local",
            reason="follow_up",
            intent=follow_up_intent,
        )

    if is_plain_analysis_chat_question(normalized_question):
        return LocalRequestResolution(
            route="local",
            reason="analysis_chat",
            intent="analysis_chat",
        )

    return LocalRequestResolution(route="provider", reason="open_chat_or_unknown")


def _conversation_intent(
    request: AgentQueryRequest,
    normalized_question: str,
) -> str | None:
    if not _looks_like_follow_up(normalized_question):
        return None
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
            intent = _intent_from_text(value)
            if intent is not None:
                return intent
    return None


def _intent_from_text(value: Any) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    # 按 _INTENT_PATTERNS 声明顺序遍历：frozenset 迭代顺序受 PYTHONHASHSEED
    # 影响，多标记文本的 follow-up 解析会跨进程非确定。
    for intent, _keywords in _INTENT_PATTERNS:
        if f"agent.{intent}" in text:
            return intent
    for workflow in list_research_workflows():
        if f"agent.{workflow.workflow_id}" in text:
            return workflow.workflow_id
    if text.startswith("agent.workflow."):
        return "analysis_chat"
    return None


def _page_default_intent(request: AgentQueryRequest | None) -> str | None:
    if request is None or request.page_context is None:
        return None
    page_id = _normalize_text(request.page_context.page_id)
    return _PAGE_DEFAULT_INTENTS.get(page_id)


def _is_page_context_question(normalized_question: str) -> bool:
    if not normalized_question:
        return False
    return any(token in normalized_question for token in _PAGE_CONTEXT_PATTERNS)


def _looks_like_follow_up(normalized_question: str) -> bool:
    if not normalized_question:
        return False
    return any(token in normalized_question for token in _FOLLOW_UP_PATTERNS)


def _is_explicit_external_provider_prompt(normalized_question: str) -> bool:
    if not normalized_question:
        return False
    return any(token in normalized_question for token in _EXTERNAL_PROVIDER_PATTERNS)


def _intent_from_question(
    normalized_question: str,
    *,
    request: AgentQueryRequest | None = None,
) -> str | None:
    if not normalized_question:
        return None
    for intent, keywords in _INTENT_PATTERNS:
        if any(keyword.lower() in normalized_question for keyword in keywords):
            return intent
        # 在 pnl_summary 原有优先级位置评估「收益(非收益率)」守卫，
        # 保持它先于 market_data、后于 product_pnl / pnl_bridge 的既有顺序。
        if intent == "pnl_summary" and _CHINESE_PNL_RETURN_PATTERN.search(normalized_question):
            return intent
    if _matches_domain_combination(
        normalized_question,
        ambiguous_terms=_GITNEXUS_AMBIGUOUS_TERMS,
        domain_terms=_GITNEXUS_DOMAIN_TERMS,
    ):
        return "gitnexus_status"
    if "duration" in normalized_question and (
        _matches_any(normalized_question, _DURATION_DOMAIN_TERMS)
        or _page_default_intent(request) == "duration_risk"
    ):
        return "duration_risk"
    if "market value" in normalized_question and (
        _matches_any(normalized_question, _MARKET_VALUE_DOMAIN_TERMS)
        or _page_default_intent(request) == "portfolio_overview"
    ):
        return "portfolio_overview"
    return None


def _matches_domain_combination(
    normalized_question: str,
    *,
    ambiguous_terms: tuple[str, ...],
    domain_terms: tuple[str, ...],
) -> bool:
    return _matches_any(normalized_question, ambiguous_terms) and _matches_any(
        normalized_question,
        domain_terms,
    )


def _matches_any(normalized_question: str, terms: tuple[str, ...]) -> bool:
    return any(_matches_term(normalized_question, term) for term in terms)


def _matches_term(normalized_question: str, term: str) -> bool:
    # ASCII 词用词边界匹配；中文等非 ASCII 词无空格分词（\w 也匹配汉字，
    # 词边界断言必然失败），用子串匹配。
    if term.isascii():
        return (
            re.search(
                rf"(?<!\w){re.escape(term)}(?!\w)",
                normalized_question,
            )
            is not None
        )
    return term in normalized_question


def _matches_analysis_pattern(normalized_question: str, pattern: str) -> bool:
    return _matches_term(normalized_question, pattern)


def _normalize_intent(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()
