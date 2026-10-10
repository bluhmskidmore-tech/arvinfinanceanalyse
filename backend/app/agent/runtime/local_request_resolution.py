from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from backend.app.agent.runtime.financial_workflow_catalog import (
    FinancialWorkflow,
    get_financial_workflow,
    is_financial_workflow_id,
    resolve_financial_workflow,
)
from backend.app.agent.runtime.ontology_bindings import (
    ONTOLOGY_BINDING_REVISION,
    get_bound_metric_entity,
    get_ontology_metric_binding,
    list_ontology_metric_bindings,
    ontology_content_revision,
)
from backend.app.agent.runtime.research_workflow_catalog import (
    ResearchWorkflow,
    get_research_workflow,
    is_research_workflow_id,
    list_research_workflows,
    resolve_research_workflow,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.ontology.loader import load_ontology_index

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

# 特异性表：key 是「更具体」的 intent，命中它时直接压制 value 里必然被一起命中的
# 泛化 intent。这些组合不是真正的多意图，不能拿去问用户。每条都必须能说清
# 「为什么后者的词表一定被前者的问法覆盖」。
_INTENT_SPECIALIZATIONS: dict[str, frozenset[str]] = {
    # 「产品损益」「损益归因/桥接/拆解」的问法必然包含泛化词「损益」。
    "product_pnl": frozenset({"pnl_summary"}),
    "pnl_bridge": frozenset({"pnl_summary"}),
    # 「久期」「利率风险」是利率风险敞口语义；「利率」同时在 market_data 词表里，
    # 但这类问法要的是风险口径，不是行情序列。
    "duration_risk": frozenset({"market_data"}),
    # 风险张量是久期/KRD 的承载视图，张量问法覆盖久期词时仍应落在张量。
    "risk_tensor": frozenset({"duration_risk"}),
    # 两个观察面意图在词表里刻意排在泛化金融词之前（见 _INTENT_PATTERNS 注释）：
    # 「盘前…损益」「策略样本外…收益」应命中观察面，而不是损益/行情/概览汇总。
    "pretrade_checklist": frozenset({"pnl_summary", "market_data", "portfolio_overview"}),
    "walk_forward_verdict": frozenset({"pnl_summary", "market_data", "portfolio_overview"}),
}

# 意图族：同族内的多命中沿用「词表顺序首命中」的既有语义（口径同源，换视图而已）；
# 跨族多命中才是真正的歧义，需要澄清。
_INTENT_FAMILIES: dict[str, str] = {
    "pnl_summary": "pnl",
    "pnl_bridge": "pnl",
    "product_pnl": "pnl",
    "portfolio_overview": "balance",
    "risk_tensor": "risk",
    "duration_risk": "risk",
    "credit_exposure": "risk",
    "market_data": "market",
    # 新闻单独成族：市场数据是数值序列，新闻是事件文本，二者同现是真歧义。
    "news": "news",
    "pretrade_checklist": "trading_observation",
    "walk_forward_verdict": "trading_observation",
    "gitnexus_status": "engineering",
}

# 保守的意图否定模式：只在关键词所在小句的紧邻前缀里成立（锚定 $），
# 避免「类别」「差别」「级别」这类含「别」的普通词被误判成否定。
_INTENT_NEGATION_PATTERNS = (
    re.compile(
        r"(?:不要|不想|不需要|不用|无需|不看|不查|不问|不关心|别看|别查|别管|不是|除了)"
        r"\s*(?:看|查(?:询|一下)?|要|显示|展示|获取|汇总|统计|关注)?\s*$"
    ),
    re.compile(
        r"\b(?:do\s+not|don't|dont|does\s+not|doesn't|without|except\s+for|other\s+than|instead\s+of)"
        r"\s+(?:need\s+|want\s+|look\s+at\s+|see\s+|show\s+|query\s+|check\s+|display\s+|"
        r"fetch\s+|get\s+|return\s+|summarize\s+|summarise\s+)?$"
    ),
)

# 指向具体某一天的自然语言相对日期。模糊词（最近/目前/当前/现在）不在此列，
# 保持既有「取最新可用报告日」语义。
_RELATIVE_DAY_PATTERNS = (
    re.compile(r"(?:今日|今天|昨日|昨天|前天|大前天|明日|明天)"),
    re.compile(r"(?:上周|上星期|本周|本星期|这周|这星期)\s*[一二三四五六日天]"),
    re.compile(r"\b(?:today|yesterday|tomorrow)\b"),
)
# 只有结果本身绑定报告日的意图才需要明确报告日；行情/新闻/盘前/策略观察面
# 的「今天」就是「最新可用」，不改其既有语义。
_REPORT_DATE_BOUND_INTENTS = frozenset(
    {
        "pnl_summary",
        "pnl_bridge",
        "product_pnl",
        "portfolio_overview",
        "risk_tensor",
        "duration_risk",
        "credit_exposure",
    }
)

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

_ONTOLOGY_DEFINITION_PATTERNS = (
    "是什么",
    "什么意思",
    "如何定义",
    "定义",
    "口径",
    "含义",
    "怎么算",
    "what is",
    "definition",
    "meaning",
    "how is",
)
_ONTOLOGY_VALUE_PATTERNS = (
    "是多少",
    "多少",
    "金额",
    "数值",
    "查询",
    "查一下",
    "给我看",
    "show",
    "how much",
)
_ONTOLOGY_VALUE_TOKEN_PATTERN = re.compile(r"(?<![a-z0-9_])value(?![a-z0-9_])")
_ONTOLOGY_UNSUPPORTED_ANALYSIS_PATTERNS = (
    "为什么",
    "原因",
    "下降",
    "上升",
    "环比",
    "同比",
    "趋势",
    "归因",
    "比较",
    "对比",
    "why",
    "decline",
    "increase",
    "trend",
    "compare",
    "versus",
)
_ONTOLOGY_PERIOD_QUERY_PATTERNS = (
    re.compile(
        r"(?:最近|近|过去|前)\s*[一二三四五六七八九十百千万\d]+\s*"
        r"(?:天|日|周|星期|个月|月|季度|季|年)"
    ),
    re.compile(
        r"\d{4}-\d{2}-\d{2}\s*(?:至|到|~|～|—|–)\s*"
        r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}(?:日|号)?)"
    ),
    re.compile(r"(?:年初|月初|季初|季度初)至今|(?:本年|本月|本季|本季度|今年)累计|累计"),
    re.compile(
        r"\b(?:last|past|previous)\s+"
        r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|thirty)\s+"
        r"(?:calendar\s+)?(?:day|week|month|quarter|year)s?\b"
    ),
    re.compile(r"\b(?:ytd|mtd|qtd|year[- ]to[- ]date|month[- ]to[- ]date|quarter[- ]to[- ]date)\b"),
)
_ONTOLOGY_DERIVED_OPERATION_PATTERNS = (
    re.compile(r"(?:占比|比例|百分比|比重|平均值?|均值|绝对值|平方|开方|中位数|最大值|最小值)"),
    re.compile(
        r"\b(?:percentage|percent|ratio|share|mean|average|median|maximum|minimum|"
        r"absolute\s+value|squared?|square\s+root)\b"
    ),
)
_ONTOLOGY_EXCLUSION_PATTERNS = (
    re.compile(r"(?:剔除|扣除|排除|去除|不含|不包括)"),
    re.compile(r"\b(?:excluding|exclude|without|except\s+for|net\s+of)\b"),
)
_ONTOLOGY_NEGATED_SELECTION_PATTERN = re.compile(
    r"(?:不要|不需要|不用|无需|别)\s*(?:查(?:询|一下)?|看|显示|展示|获取|计算)?\s*"
    r"(?:mtr-pnl-(?:001|002|005)|514|516|interest_income_514|fair_value_change_516|"
    r"total_pnl|formal total pnl|利息收入(?:（?514）?)?|公允价值变动(?:（?516）?)?|正式总损益)"
    r"|\b(?:do\s+not|don't|dont)\s+(?:query|show|fetch|get|calculate|use|display|return|retrieve)\s+"
    r"(?:the\s+)?(?:mtr-pnl-(?:001|002|005)|514|516|interest_income_514|"
    r"fair_value_change_516|total_pnl|formal total pnl)\b"
)
_ONTOLOGY_ALLOWED_VALUE_FILLERS = (
    re.compile(
        r"(?:请问|请|麻烦|帮我|我想知道|想知道|只查询|只查|查询|查一下|查看|看一下|"
        r"给我看|显示|展示|获取|返回|告诉我|报告日|截至|截止|当日|这一天|"
        r"币种为人民币|人民币口径|人民币|是多少|多少|数值|金额|值|的|为)"
    ),
    re.compile(
        r"\b(?:please|show|query|look\s+up|display|get|fetch|return|tell|give|me|"
        r"what|how\s+much|the|value|amount|for|on|at|as|of|is|was|only|but|instead|cny)\b"
    ),
    re.compile(r"[\s，,。.!！?？;；:：()（）\[\]【】]+"),
)
_ISO_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")
_ONTOLOGY_CODE_METRICS = {
    "514": "MTR-PNL-001",
    "516": "MTR-PNL-002",
}
_UNSUPPORTED_PNL_METRIC_PATTERNS = (
    re.compile(r"(?<![a-z0-9_])517(?![a-z0-9_])"),
    re.compile(r"(?<![a-z0-9_])capital_gain_517(?![a-z0-9_])"),
    re.compile(r"(?<![a-z0-9_])capital gains?(?![a-z0-9_])"),
    re.compile(r"(?:资本利得|资本收益|处置损益)"),
)
_UNSUPPORTED_NATURAL_SCOPE_PATTERNS = (
    re.compile(
        r"(?:组合|账户|产品|机构|固收|固定收益|债券|股票|基金|资产|负债|"
        r"非标|金融投资|交易台|台账|账簿|账套|总账|成本中心|业务类型|来源类型|"
        r"按券|单券|券种)"
    ),
    re.compile(
        r"(?:美元|美金|欧元|日元|港币|英镑|外币|原币|综本|综合本币|本外币|"
        r"(?:按|分|各)币种|币种(?:维度|分别))"
    ),
    re.compile(
        r"(?<![a-z0-9_])(?:usd|eur|jpy|hkd|gbp|cnx|portfolio|account|product|fund|asset|liability|bond|fixed income|fi|native currency|nonstd|non[- ]?standard|financial investments?|trading desks?|desk|ledgers?|books?|cost centers?|business types?|source kinds?|instruments?|securit(?:y|ies)|security types?|ac|fvoci|fvtpl)"
        r"(?![a-z0-9_])"
    ),
)
_CONTEXT_SCOPE_FILTER_KEYS = frozenset(
    {
        "portfolio_id",
        "portfolio_ids",
        "portfolio_name",
        "account_id",
        "account_ids",
        "account_name",
        "product_id",
        "product_ids",
        "product_name",
        "fund_id",
        "fund_name",
        "asset_class",
        "book_id",
        "book_name",
        "ledger",
        "ledger_id",
        "ledger_name",
        "cost_center",
        "cost_center_id",
        "cost_center_ids",
        "cost_center_name",
        "source_kind",
        "source_kinds",
        "source_scope",
        "nonstd",
        "nonstd_scope",
        "fi_scope",
        "formal_fi",
        "investment_scope",
        "financial_investment",
        "business_type",
        "business_types",
        "business_type_primary",
        "trading_desk",
        "trading_desk_id",
        "trading_desk_ids",
        "trading_desk_name",
        "desk",
        "desk_id",
        "desk_name",
        "instrument",
        "instrument_id",
        "instrument_ids",
        "instrument_code",
        "instrument_codes",
        "instrument_name",
        "security_id",
        "security_code",
        "security_type",
        "bond_code",
        "bond_type",
        "currency_group",
        "accounting_basis",
        "selected_rows",
        "currency",
        "currency_code",
        "currency_basis",
        "position_scope",
    }
)

_LOCAL_INTENTS = frozenset(intent for intent, _keywords in _INTENT_PATTERNS)

SEMANTIC_EXECUTION_CONTEXT_KEY = "__moss_semantic_execution_v1"
SEMANTIC_EXECUTION_SCHEMA_VERSION = 1
ONTOLOGY_PARSER_REVISION = "ontology-local-parser-v3"
ONTOLOGY_UNAVAILABLE_REVISION = "unavailable"

SemanticStatus = Literal[
    "resolved",
    "clarification_required",
    "unsupported",
    "unavailable",
]
SemanticOperation = Literal["definition", "value"]


@dataclass(frozen=True)
class LocalRequestResolution:
    route: Literal["local", "provider"]
    reason: str
    intent: str | None = None
    financial_workflow: FinancialWorkflow | None = None
    research_workflow: ResearchWorkflow | None = None
    semantic_status: SemanticStatus | None = None
    semantic_operation: SemanticOperation | None = None
    metric_id: str | None = None
    metric_candidates: tuple[str, ...] = ()
    semantic_reason_code: str | None = None
    report_date: str | None = None
    # 关键词路由澄清用的候选业务 intent（非本体指标），仅在本进程内传递：
    # 语义快照只固化本体字段，不携带该列表。
    intent_candidates: tuple[str, ...] = ()


def build_semantic_execution_snapshot(
    resolution: LocalRequestResolution,
    request: AgentQueryRequest,
) -> dict[str, Any] | None:
    """Build a server-owned, JSON-safe semantic execution pin.

    Existing intents and provider/open-chat requests intentionally return no
    snapshot. Only ontology-routed requests need version-pinned execution.
    """

    if resolution.route != "local" or resolution.semantic_status is None:
        return None
    required_resources: list[str] = []
    if (
        resolution.semantic_status == "resolved"
        and resolution.semantic_operation == "value"
        and resolution.metric_id
    ):
        binding = get_ontology_metric_binding(resolution.metric_id)
        if binding is None:
            raise ValueError(f"Unknown ontology metric binding: {resolution.metric_id}")
        required_resources.append(binding.required_resource)
    if resolution.semantic_status == "unavailable":
        try:
            ontology_revision = ontology_content_revision()
        except (OSError, TypeError, ValueError):
            ontology_revision = ONTOLOGY_UNAVAILABLE_REVISION
    else:
        ontology_revision = ontology_content_revision()
    request_scope = (
        {
            "basis": request.basis,
            "position_scope": request.position_scope,
            "currency_basis": ontology_currency_basis(request),
            "report_date": resolution.report_date,
        }
        if resolution.semantic_status == "resolved"
        and resolution.semantic_operation == "value"
        else None
    )
    return {
        "schema_version": SEMANTIC_EXECUTION_SCHEMA_VERSION,
        "route": "local",
        "status": resolution.semantic_status,
        "operation": resolution.semantic_operation,
        "metric_id": resolution.metric_id,
        "candidate_metric_ids": list(resolution.metric_candidates),
        "intent": resolution.intent,
        "report_date": resolution.report_date,
        "reason": resolution.reason,
        "reason_code": resolution.semantic_reason_code,
        "required_resources": required_resources,
        "request_scope": request_scope,
        "ontology_revision": ontology_revision,
        "binding_revision": ONTOLOGY_BINDING_REVISION,
        "parser_revision": ONTOLOGY_PARSER_REVISION,
    }


def validate_semantic_execution_snapshot(
    value: Any,
    *,
    require_current_versions: bool = True,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("semantic execution snapshot must be an object")

    expected_keys = {
        "schema_version",
        "route",
        "status",
        "operation",
        "metric_id",
        "candidate_metric_ids",
        "intent",
        "report_date",
        "reason",
        "reason_code",
        "required_resources",
        "request_scope",
        "ontology_revision",
        "binding_revision",
        "parser_revision",
    }
    if set(value) != expected_keys:
        raise ValueError("semantic execution snapshot has an unexpected shape")
    if value.get("schema_version") != SEMANTIC_EXECUTION_SCHEMA_VERSION:
        raise ValueError("semantic execution snapshot schema version is unsupported")
    if value.get("route") != "local":
        raise ValueError("semantic execution snapshot route must be local")

    status = value.get("status")
    if status not in {"resolved", "clarification_required", "unsupported", "unavailable"}:
        raise ValueError("semantic execution snapshot status is invalid")
    operation = value.get("operation")
    if operation not in {None, "definition", "value"}:
        raise ValueError("semantic execution snapshot operation is invalid")

    metric_id = _optional_snapshot_text(value.get("metric_id"))
    candidates_value = value.get("candidate_metric_ids")
    if not isinstance(candidates_value, list) or not all(
        isinstance(candidate, str) and candidate.strip() for candidate in candidates_value
    ):
        raise ValueError("semantic execution snapshot candidates are invalid")
    candidates = [candidate.strip().upper() for candidate in candidates_value]
    if len(candidates) != len(set(candidates)):
        raise ValueError("semantic execution snapshot candidates must be unique")
    if any(get_ontology_metric_binding(candidate) is None for candidate in candidates):
        raise ValueError("semantic execution snapshot contains an unbound metric candidate")
    if metric_id is not None:
        metric_id = metric_id.upper()
        if get_ontology_metric_binding(metric_id) is None:
            raise ValueError("semantic execution snapshot metric is not bound")

    intent = _optional_snapshot_text(value.get("intent"))
    allowed_intents = {
        "pnl_summary",
        "ontology_definition",
        "ontology_clarification",
        "ontology_unsupported",
        "ontology_unavailable",
    }
    if intent not in allowed_intents:
        raise ValueError("semantic execution snapshot intent is invalid")
    expected_intent = {
        ("resolved", "definition"): "ontology_definition",
        ("resolved", "value"): "pnl_summary",
        ("clarification_required", None): "ontology_clarification",
        ("unsupported", None): "ontology_unsupported",
        ("unsupported", "value"): "ontology_unsupported",
        ("unavailable", None): "ontology_unavailable",
    }.get((status, operation))
    if intent != expected_intent:
        raise ValueError("semantic execution snapshot intent conflicts with status/operation")

    report_date = _optional_snapshot_text(value.get("report_date"))
    if report_date is not None:
        _validate_iso_report_date(report_date)
    if status == "resolved" and operation == "value":
        if metric_id is None or report_date is None:
            raise ValueError("resolved value snapshot requires metric_id and report_date")
    if status == "resolved" and operation == "definition" and metric_id is None:
        raise ValueError("resolved definition snapshot requires metric_id")

    resources_value = value.get("required_resources")
    if not isinstance(resources_value, list) or not all(
        isinstance(resource, str) and resource.strip() for resource in resources_value
    ):
        raise ValueError("semantic execution snapshot resources are invalid")
    resources = [resource.strip() for resource in resources_value]
    expected_resources = ["pnl"] if intent == "pnl_summary" else []
    if resources != expected_resources:
        raise ValueError("semantic execution snapshot resources conflict with intent")

    request_scope_value = value.get("request_scope")
    request_scope: dict[str, str | None] | None = None
    if intent == "pnl_summary":
        if not isinstance(request_scope_value, dict) or set(request_scope_value) != {
            "basis",
            "position_scope",
            "currency_basis",
            "report_date",
        }:
            raise ValueError("semantic execution snapshot request scope is invalid")
        request_scope = {
            "basis": _required_snapshot_text(request_scope_value.get("basis"), "basis"),
            "position_scope": _required_snapshot_text(
                request_scope_value.get("position_scope"), "position_scope"
            ),
            "currency_basis": _required_snapshot_text(
                request_scope_value.get("currency_basis"), "currency_basis"
            ),
            "report_date": _optional_snapshot_text(request_scope_value.get("report_date")),
        }
        if (
            request_scope["basis"] != "formal"
            or request_scope["position_scope"] != "all"
            or request_scope["currency_basis"] != "CNY"
            or request_scope["report_date"] != report_date
        ):
            raise ValueError("semantic execution snapshot request scope is unsupported")
    elif request_scope_value is not None:
        raise ValueError("non-executable semantic snapshot cannot carry request scope")

    reason = _required_snapshot_text(value.get("reason"), "reason")
    reason_code = _required_snapshot_text(value.get("reason_code"), "reason_code")
    ontology_revision = _required_snapshot_text(
        value.get("ontology_revision"), "ontology_revision"
    )
    binding_revision = _required_snapshot_text(
        value.get("binding_revision"), "binding_revision"
    )
    parser_revision = _required_snapshot_text(
        value.get("parser_revision"), "parser_revision"
    )
    if require_current_versions:
        if status == "unavailable":
            if ontology_revision == ONTOLOGY_UNAVAILABLE_REVISION:
                try:
                    ontology_content_revision()
                except (OSError, TypeError, ValueError):
                    pass
                else:
                    raise ValueError(
                        "semantic execution snapshot versions are no longer current"
                    )
            else:
                try:
                    current_ontology_revision = ontology_content_revision()
                except (OSError, TypeError, ValueError) as exc:
                    raise ValueError("current ontology revision is unavailable") from exc
                if ontology_revision != current_ontology_revision:
                    raise ValueError(
                        "semantic execution snapshot versions are no longer current"
                    )
        else:
            try:
                current_ontology_revision = ontology_content_revision()
            except (OSError, TypeError, ValueError) as exc:
                raise ValueError("current ontology revision is unavailable") from exc
            if ontology_revision != current_ontology_revision:
                raise ValueError("semantic execution snapshot versions are no longer current")
        if (
            binding_revision != ONTOLOGY_BINDING_REVISION
            or parser_revision != ONTOLOGY_PARSER_REVISION
        ):
            raise ValueError("semantic execution snapshot versions are no longer current")

    return {
        "schema_version": SEMANTIC_EXECUTION_SCHEMA_VERSION,
        "route": "local",
        "status": status,
        "operation": operation,
        "metric_id": metric_id,
        "candidate_metric_ids": candidates,
        "intent": intent,
        "report_date": report_date,
        "reason": reason,
        "reason_code": reason_code,
        "required_resources": resources,
        "request_scope": request_scope,
        "ontology_revision": ontology_revision,
        "binding_revision": binding_revision,
        "parser_revision": parser_revision,
    }


def resolution_from_semantic_execution_snapshot(value: Any) -> LocalRequestResolution:
    snapshot = validate_semantic_execution_snapshot(value)
    return LocalRequestResolution(
        route="local",
        reason=str(snapshot["reason"]),
        intent=str(snapshot["intent"]),
        semantic_status=snapshot["status"],
        semantic_operation=snapshot["operation"],
        metric_id=snapshot["metric_id"],
        metric_candidates=tuple(snapshot["candidate_metric_ids"]),
        semantic_reason_code=str(snapshot["reason_code"]),
        report_date=snapshot["report_date"],
    )


def validate_semantic_execution_request(
    request: AgentQueryRequest,
    *,
    require_current_versions: bool = True,
) -> dict[str, Any]:
    snapshot = validate_semantic_execution_snapshot(
        request.context.get(SEMANTIC_EXECUTION_CONTEXT_KEY),
        require_current_versions=require_current_versions,
    )
    if snapshot["status"] == "resolved" and snapshot["operation"] == "value":
        scope_errors = ontology_request_scope_errors(request)
        if scope_errors:
            raise ValueError(
                "semantic execution request scope conflicts with its snapshot: "
                + ", ".join(scope_errors)
            )
        pinned_scope = snapshot.get("request_scope")
        current_scope = {
            "basis": request.basis,
            "position_scope": request.position_scope,
            "currency_basis": ontology_currency_basis(request),
            "report_date": snapshot["report_date"],
        }
        if pinned_scope != current_scope:
            raise ValueError(
                "semantic execution request scope conflicts with its snapshot"
            )
        report_date, date_reason = _semantic_report_date(
            request,
            _normalize_text(request.question),
        )
        if date_reason is not None or report_date != snapshot["report_date"]:
            raise ValueError(
                "semantic execution request report_date conflicts with its snapshot"
            )
        current_resolution = _resolve_ontology_request(
            request,
            _normalize_text(request.question),
        )
        if (
            current_resolution is None
            or current_resolution.semantic_status != "resolved"
            or current_resolution.semantic_operation != "value"
            or current_resolution.metric_id != snapshot["metric_id"]
            or current_resolution.report_date != snapshot["report_date"]
        ):
            raise ValueError(
                "semantic execution request meaning conflicts with its snapshot"
            )
    return snapshot


def pin_semantic_execution_request(
    request: AgentQueryRequest,
) -> tuple[AgentQueryRequest, LocalRequestResolution]:
    """Resolve once and attach a server-owned execution snapshot when needed."""

    if SEMANTIC_EXECUTION_CONTEXT_KEY in request.context:
        raise ValueError("semantic execution context key is reserved for the server")
    resolution = resolve_local_request(request)
    snapshot = build_semantic_execution_snapshot(resolution, request)
    if snapshot is None:
        return request, resolution
    snapshot = validate_semantic_execution_snapshot(snapshot)
    update: dict[str, Any] = {
        "context": {
            **request.context,
            SEMANTIC_EXECUTION_CONTEXT_KEY: snapshot,
        }
    }
    request_scope = snapshot.get("request_scope")
    if isinstance(request_scope, dict):
        # 未显式声明币种时把服务器端的有效口径写进 pinned 请求，让下游取数与
        # 口径校验看到与快照一致的 CNY，而不是 schema 遗留默认值 CNX。
        update["currency_basis"] = request_scope["currency_basis"]
    pinned = request.model_copy(update=update)
    validate_semantic_execution_request(pinned)
    return pinned, resolution


def _optional_snapshot_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("semantic execution snapshot text fields must be strings")
    normalized = value.strip()
    return normalized or None


def _required_snapshot_text(value: Any, field_name: str) -> str:
    normalized = _optional_snapshot_text(value)
    if normalized is None:
        raise ValueError(f"semantic execution snapshot {field_name} is required")
    return normalized


def _validate_iso_report_date(value: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError("report_date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("report_date must be a real calendar date") from exc


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
    if SEMANTIC_EXECUTION_CONTEXT_KEY in request.context:
        validate_semantic_execution_request(request)
        return resolution_from_semantic_execution_snapshot(
            request.context.get(SEMANTIC_EXECUTION_CONTEXT_KEY)
        )

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
        if explicit_intent == "pnl_summary":
            semantic_resolution = _resolve_ontology_request(request, normalized_question)
            if semantic_resolution is not None:
                if semantic_resolution.semantic_operation == "definition":
                    return LocalRequestResolution(
                        route="local",
                        reason="ontology_clarification",
                        intent="ontology_clarification",
                        semantic_status="clarification_required",
                        metric_id=semantic_resolution.metric_id,
                        metric_candidates=semantic_resolution.metric_candidates,
                        semantic_reason_code="explicit_intent_semantic_conflict",
                    )
                return semantic_resolution
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

    ontology_resolution = _resolve_ontology_request(request, normalized_question)
    if ontology_resolution is not None:
        return ontology_resolution

    keyword_resolution = _keyword_intent_resolution(request, normalized_question)
    if keyword_resolution is not None:
        return keyword_resolution

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
        if request.routing_surface == "standalone_workbench":
            return LocalRequestResolution(
                route="provider",
                reason="standalone_workbench_chat",
            )
        return LocalRequestResolution(
            route="local",
            reason="analysis_chat",
            intent="analysis_chat",
        )

    return LocalRequestResolution(route="provider", reason="open_chat_or_unknown")


def _resolve_ontology_request(
    request: AgentQueryRequest,
    normalized_question: str,
) -> LocalRequestResolution | None:
    if _looks_like_unsupported_pnl_metric(normalized_question):
        return LocalRequestResolution(
            route="local",
            reason="ontology_unsupported",
            intent="ontology_unsupported",
            semantic_status="unsupported",
            semantic_operation="value",
            semantic_reason_code="unsupported_metric",
        )
    try:
        candidates = _bound_metric_candidates(normalized_question)
    except (OSError, TypeError, ValueError):
        if not _looks_like_ontology_pnl_question(normalized_question):
            return None
        return LocalRequestResolution(
            route="local",
            reason="ontology_unavailable",
            intent="ontology_unavailable",
            semantic_status="unavailable",
            semantic_reason_code="ontology_unavailable",
        )

    if not candidates and _looks_like_negated_ontology_pnl_question(normalized_question):
        return LocalRequestResolution(
            route="local",
            reason="ontology_clarification",
            intent="ontology_clarification",
            semantic_status="clarification_required",
            semantic_reason_code="negated_metric_reference",
        )
    if not candidates and _is_ambiguous_return_value_question(normalized_question):
        candidates = tuple(
            binding.metric_id for binding in list_ontology_metric_bindings()
        )
    if not candidates and _looks_like_ontology_pnl_question(normalized_question):
        return LocalRequestResolution(
            route="local",
            reason="ontology_clarification",
            intent="ontology_clarification",
            semantic_status="clarification_required",
            semantic_reason_code="unresolved_metric_reference",
        )
    if not candidates:
        return None

    if len(candidates) > 1:
        return LocalRequestResolution(
            route="local",
            reason="ontology_clarification",
            intent="ontology_clarification",
            semantic_status="clarification_required",
            metric_candidates=candidates[:3],
            semantic_reason_code="multiple_metric_candidates",
        )

    metric_id = candidates[0]
    if _requires_metric_alias_clarification(request, normalized_question, candidates):
        return LocalRequestResolution(
            route="local",
            reason="ontology_clarification",
            intent="ontology_clarification",
            semantic_status="clarification_required",
            metric_candidates=candidates,
            semantic_reason_code="ambiguous_metric_alias",
        )

    binding = get_ontology_metric_binding(metric_id)
    if binding is None or get_bound_metric_entity(metric_id) is None:
        return LocalRequestResolution(
            route="local",
            reason="ontology_unavailable",
            intent="ontology_unavailable",
            semantic_status="unavailable",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code="metric_binding_unavailable",
        )

    unsupported_operation = _ontology_unsupported_value_reason(normalized_question)
    if unsupported_operation is not None:
        return LocalRequestResolution(
            route="local",
            reason="ontology_unsupported",
            intent="ontology_unsupported",
            semantic_status="unsupported",
            semantic_operation="value",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code=unsupported_operation,
        )

    if any(pattern in normalized_question for pattern in _ONTOLOGY_UNSUPPORTED_ANALYSIS_PATTERNS):
        return LocalRequestResolution(
            route="local",
            reason="ontology_unsupported",
            intent="ontology_unsupported",
            semantic_status="unsupported",
            semantic_operation="value",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code="unsupported_comparison_or_attribution",
        )

    definition_requested = any(
        pattern in normalized_question for pattern in _ONTOLOGY_DEFINITION_PATTERNS
    )
    value_requested = any(
        pattern in normalized_question for pattern in _ONTOLOGY_VALUE_PATTERNS
    ) or bool(_ONTOLOGY_VALUE_TOKEN_PATTERN.search(normalized_question))
    if definition_requested and value_requested:
        return LocalRequestResolution(
            route="local",
            reason="ontology_clarification",
            intent="ontology_clarification",
            semantic_status="clarification_required",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code="operation_conflict",
        )
    if definition_requested:
        return LocalRequestResolution(
            route="local",
            reason="ontology_metric_definition",
            intent="ontology_definition",
            semantic_status="resolved",
            semantic_operation="definition",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code="metric_definition_resolved",
        )

    unsupported_filter_keys = ontology_request_scope_errors(request)
    if unsupported_filter_keys:
        return LocalRequestResolution(
            route="local",
            reason="ontology_unsupported",
            intent="ontology_unsupported",
            semantic_status="unsupported",
            semantic_operation="value",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code="unsupported_query_scope",
        )

    report_date, date_reason = _semantic_report_date(request, normalized_question)
    if date_reason is not None:
        return LocalRequestResolution(
            route="local",
            reason="ontology_clarification",
            intent="ontology_clarification",
            semantic_status="clarification_required",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code=date_reason,
        )
    if value_requested or report_date is not None:
        if report_date is None:
            return LocalRequestResolution(
                route="local",
                reason="ontology_clarification",
                intent="ontology_clarification",
                semantic_status="clarification_required",
                metric_id=metric_id,
                metric_candidates=(metric_id,),
                semantic_reason_code="report_date_required",
            )
        if not _is_supported_raw_metric_value_question(
            normalized_question,
            metric_id,
        ):
            return LocalRequestResolution(
                route="local",
                reason="ontology_unsupported",
                intent="ontology_unsupported",
                semantic_status="unsupported",
                semantic_operation="value",
                metric_id=metric_id,
                metric_candidates=(metric_id,),
                semantic_reason_code="unsupported_query_scope",
            )
        return LocalRequestResolution(
            route="local",
            reason="ontology_metric_value",
            intent=binding.intent,
            semantic_status="resolved",
            semantic_operation="value",
            metric_id=metric_id,
            metric_candidates=(metric_id,),
            semantic_reason_code="metric_value_resolved",
            report_date=report_date,
        )

    return LocalRequestResolution(
        route="local",
        reason="ontology_clarification",
        intent="ontology_clarification",
        semantic_status="clarification_required",
        metric_id=metric_id,
        metric_candidates=(metric_id,),
        semantic_reason_code="operation_required",
    )


def ontology_currency_basis(request: AgentQueryRequest) -> str:
    """本体数值路径的有效币种口径。

    `AgentQueryRequest.currency_basis` 的 schema 默认值是历史遗留的综本口径
    `CNX`，而本体首期只承诺人民币口径。因此只有调用方**显式**设置过该字段时
    才把它当作约束；未显式设置时按 `CNY` 处理，语义快照也固化为 `CNY`，
    避免任何没传币种的调用方在取数前被拒。
    """

    if "currency_basis" in request.model_fields_set:
        return request.currency_basis
    return "CNY"


def ontology_request_scope_errors(request: AgentQueryRequest) -> list[str]:
    containers: list[tuple[str, dict[str, Any]]] = [("filters", request.filters)]
    current_filters = request.context.get("current_filters")
    if isinstance(current_filters, dict):
        containers.append(("context.current_filters", current_filters))
    elif _semantic_filter_value_present(current_filters):
        containers.append(("context.current_filters", {"invalid": current_filters}))
    if request.page_context is not None:
        containers.append(("page_context.current_filters", request.page_context.current_filters))

    unsupported: set[str] = set()
    for container_name, container in containers:
        for key, value in container.items():
            if key in {"report_date", "date"} or not _semantic_filter_value_present(value):
                continue
            unsupported.add(f"{container_name}.{key}")
    for key in _CONTEXT_SCOPE_FILTER_KEYS:
        if _semantic_filter_value_present(request.context.get(key)):
            unsupported.add(f"context.{key}")
    if request.page_context is not None and request.page_context.selected_rows:
        unsupported.add("page_context.selected_rows")
    if (
        request.page_context is not None
        and request.page_context.context_note
        and _has_unsupported_natural_language_scope(
            _normalize_text(request.page_context.context_note)
        )
    ):
        unsupported.add("page_context.context_note")
    if _has_unsupported_natural_language_scope(_normalize_text(request.question)):
        unsupported.add("question_scope")
    if request.position_scope != "all":
        unsupported.add("position_scope")
    if ontology_currency_basis(request) != "CNY":
        unsupported.add("currency_basis")
    if request.basis != "formal":
        unsupported.add("basis")
    return sorted(unsupported)


def _semantic_filter_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _looks_like_unsupported_pnl_metric(normalized_question: str) -> bool:
    return any(
        pattern.search(normalized_question)
        for pattern in _UNSUPPORTED_PNL_METRIC_PATTERNS
    )


def _has_unsupported_natural_language_scope(normalized_question: str) -> bool:
    return any(
        pattern.search(normalized_question)
        for pattern in _UNSUPPORTED_NATURAL_SCOPE_PATTERNS
    )


def _ontology_unsupported_value_reason(normalized_question: str) -> str | None:
    if any(pattern.search(normalized_question) for pattern in _ONTOLOGY_PERIOD_QUERY_PATTERNS):
        return "unsupported_period_query"
    if any(
        pattern.search(normalized_question)
        for pattern in _ONTOLOGY_DERIVED_OPERATION_PATTERNS
    ):
        return "unsupported_derived_operation"
    if any(pattern.search(normalized_question) for pattern in _ONTOLOGY_EXCLUSION_PATTERNS):
        return "unsupported_query_scope"
    return None


def _is_supported_raw_metric_value_question(
    normalized_question: str,
    metric_id: str,
) -> bool:
    """Accept only a single metric's untransformed value plus ordinary request filler."""

    entity = get_bound_metric_entity(metric_id)
    if entity is None:
        return False
    residual = _ONTOLOGY_NEGATED_SELECTION_PATTERN.sub(" ", normalized_question)
    residual = _ISO_DATE_PATTERN.sub(" ", residual)
    metric_terms = {
        str(term or "").casefold().strip()
        for term in (entity.entity_id, entity.name, *entity.aliases)
        if str(term or "").strip()
    }
    metric_terms.update(
        account_code
        for account_code, bound_metric_id in _ONTOLOGY_CODE_METRICS.items()
        if bound_metric_id == metric_id
    )
    for term in sorted(metric_terms, key=len, reverse=True):
        if term.isascii():
            residual = re.sub(
                rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])",
                " ",
                residual,
            )
        else:
            residual = residual.replace(term, " ")
    for pattern in _ONTOLOGY_ALLOWED_VALUE_FILLERS:
        residual = pattern.sub(" ", residual)
    return not residual.strip()


def _bound_metric_candidates(normalized_question: str) -> tuple[str, ...]:
    resolved_ids = {
        entity.entity_id
        for entity in load_ontology_index().resolve_from_text(normalized_question)
        if _has_explicit_ontology_term(normalized_question, entity)
    }
    for account_code, metric_id in _ONTOLOGY_CODE_METRICS.items():
        if _has_unnegated_account_code(normalized_question, account_code):
            resolved_ids.add(metric_id)
    return tuple(
        binding.metric_id
        for binding in list_ontology_metric_bindings()
        if binding.metric_id in resolved_ids
    )


def _has_explicit_ontology_term(normalized_question: str, entity: Any) -> bool:
    for raw_term in (entity.entity_id, entity.name, *entity.aliases):
        term = str(raw_term or "").casefold().strip()
        if not term:
            continue
        if term.isascii():
            matches = re.finditer(
                rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])",
                normalized_question,
            )
        else:
            matches = re.finditer(re.escape(term), normalized_question)
        if any(
            not _is_negated_ontology_term(normalized_question, match.start())
            for match in matches
        ):
            return True
    return False


def _has_unnegated_account_code(normalized_question: str, account_code: str) -> bool:
    for match in re.finditer(
        rf"(?<![a-z0-9_]){re.escape(account_code)}(?![a-z0-9_])",
        normalized_question,
    ):
        if not _is_negated_ontology_term(normalized_question, match.start()):
            return True
    return False


def _is_negated_ontology_term(normalized_question: str, start: int) -> bool:
    clause_start = max(
        (normalized_question.rfind(separator, 0, start) for separator in "，,；;。.!！？?\n"),
        default=-1,
    )
    prefix = normalized_question[clause_start + 1 : start]
    if re.search(r"(?:并?不是|非)\s*$", prefix) or re.search(
        r"(?:non[- ]|not\s+)$",
        prefix,
    ):
        return True

    negative_positions = [
        match.start()
        for pattern in (
            re.compile(
                r"(?:不要|不需要|不用|无需|别)\s*"
                r"(?:查(?:询|一下)?|看|显示|展示|获取|计算)?"
            ),
            re.compile(
                r"\b(?:do\s+not|don't|dont)\s+"
                r"(?:query|show|fetch|get|calculate|use|display|return|retrieve)\b"
            ),
        )
        for match in pattern.finditer(prefix)
    ]
    if not negative_positions:
        return False
    positive_positions = [
        match.start()
        for pattern in (
            re.compile(r"(?:只|改为|改成|而是)\s*(?:查(?:询|一下)?|看|显示|展示|获取)"),
            re.compile(r"\b(?:but|instead)\s+(?:query|show|fetch|get|display|return)\b"),
        )
        for match in pattern.finditer(prefix)
    ]
    return max(negative_positions) > max(positive_positions, default=-1)


def _looks_like_ontology_pnl_question(normalized_question: str) -> bool:
    ontology_terms = (
        "mtr-pnl-",
        "利息收入",
        "公允价值变动",
        "正式总损益",
        "interest_income_514",
        "fair_value_change_516",
        "total_pnl",
        "formal total pnl",
    )
    if any(term in normalized_question for term in ontology_terms):
        return True
    return any(
        re.search(rf"(?<!\d){account_code}(?!\d)", normalized_question)
        for account_code in _ONTOLOGY_CODE_METRICS
    )


def _looks_like_negated_ontology_pnl_question(normalized_question: str) -> bool:
    ontology_terms = (
        "正式总损益",
        "利息收入",
        "公允价值变动",
        "total_pnl",
        "formal total pnl",
        "interest_income_514",
        "fair_value_change_516",
        "mtr-pnl-001",
        "mtr-pnl-002",
        "mtr-pnl-005",
    )
    for term in ontology_terms:
        pattern = (
            rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])"
            if term.isascii()
            else re.escape(term)
        )
        if any(
            _is_negated_ontology_term(normalized_question, match.start())
            for match in re.finditer(pattern, normalized_question)
        ):
            return True
    return any(
        _is_negated_ontology_term(normalized_question, match.start())
        for account_code in _ONTOLOGY_CODE_METRICS
        for match in re.finditer(
            rf"(?<![a-z0-9_]){re.escape(account_code)}(?![a-z0-9_])",
            normalized_question,
        )
    )


def _is_ambiguous_return_value_question(normalized_question: str) -> bool:
    if "收益率" in normalized_question or not re.search(r"收益(?!率)", normalized_question):
        return False
    if not any(pattern in normalized_question for pattern in _ONTOLOGY_VALUE_PATTERNS):
        return False
    specific_qualifiers = (
        "产品",
        "投资",
        "债券",
        "组合",
        "资产",
        "负债",
        "基金",
        "净收益",
        "总收益",
        "正式总损益",
        "利息收入",
        "公允价值变动",
    )
    return not any(qualifier in normalized_question for qualifier in specific_qualifiers)


def _requires_metric_alias_clarification(
    request: AgentQueryRequest,
    normalized_question: str,
    candidates: tuple[str, ...],
) -> bool:
    if candidates != ("MTR-PNL-001",) or "利息收入" not in normalized_question:
        return False
    explicit_terms = (
        "514",
        "mtr-pnl-001",
        "interest_income_514",
        "formal pnl",
        "正式损益",
    )
    if any(term in normalized_question for term in explicit_terms):
        return False
    page_id = ""
    if request.page_context is not None:
        page_id = _normalize_text(request.page_context.page_id)
    if not page_id:
        page_id = _normalize_text(request.context.get("page_id"))
    return page_id not in {"pnl-attribution", "pnl-overview"}


def _semantic_report_date(
    request: AgentQueryRequest,
    normalized_question: str,
) -> tuple[str | None, str | None]:
    raw_dates: list[str] = []
    current_filters = request.context.get("current_filters")
    containers: list[dict[str, Any]] = [request.filters, request.context]
    if isinstance(current_filters, dict):
        containers.append(current_filters)
    if request.page_context is not None:
        containers.append(request.page_context.current_filters)
    for container in containers:
        for key in ("report_date", "date"):
            value = container.get(key)
            if value not in (None, ""):
                raw_dates.append(str(value).strip())
    raw_dates.extend(_ISO_DATE_PATTERN.findall(normalized_question))
    if not raw_dates:
        return None, None

    normalized_dates: list[str] = []
    for raw_date in raw_dates:
        try:
            normalized = _validate_iso_report_date(raw_date)
        except ValueError:
            return None, "invalid_report_date"
        if normalized not in normalized_dates:
            normalized_dates.append(normalized)
    if len(normalized_dates) != 1:
        return None, "report_date_conflict"
    return normalized_dates[0], None


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
        intent = _intent_from_text(turn.get("result_kind"))
        if intent is not None:
            return intent
        intent = _intent_from_trace_id(turn.get("trace_id"))
        if intent is not None:
            return intent
    return None


def _intent_from_text(value: Any) -> str | None:
    text = _normalize_text(value)
    if not text.startswith("agent."):
        return None
    marker = text.removeprefix("agent.")
    if marker in _LOCAL_INTENTS:
        return marker
    for workflow in list_research_workflows():
        if marker == workflow.workflow_id:
            return workflow.workflow_id
    if marker.startswith("workflow."):
        workflow_id = marker.removeprefix("workflow.")
        if (
            get_financial_workflow(workflow_id) is not None
            or get_research_workflow(workflow_id) is not None
        ):
            return "analysis_chat"
    return None


def _intent_from_trace_id(value: Any) -> str | None:
    text = _normalize_text(value)
    trace_suffix = r"[0-9a-f]{12}"
    for intent in _LOCAL_INTENTS:
        if re.fullmatch(rf"tr_agent_{re.escape(intent)}_{trace_suffix}", text):
            return intent
    for workflow in list_research_workflows():
        if re.fullmatch(
            rf"tr_agent_{re.escape(workflow.workflow_id)}_{trace_suffix}",
            text,
        ):
            return workflow.workflow_id
    workflow_match = re.fullmatch(
        rf"tr_agent_workflow_(?P<workflow_id>[a-z0-9_]+)_{trace_suffix}",
        text,
    )
    if workflow_match is not None:
        workflow_id = workflow_match.group("workflow_id")
        if (
            get_financial_workflow(workflow_id) is not None
            or get_research_workflow(workflow_id) is not None
        ):
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
    """词表路由的首选 intent（按 _INTENT_PATTERNS 顺序），无命中返回 None。"""

    candidates = _intent_candidates_from_question(normalized_question, request=request)
    return candidates[0] if candidates else None


def _intent_candidates_from_question(
    normalized_question: str,
    *,
    request: AgentQueryRequest | None = None,
) -> tuple[str, ...]:
    """按 _INTENT_PATTERNS 顺序收集全部命中的 intent（去重，保序）。

    与旧实现的差别只有两点：命中即返回改为收集全部命中；裸子串匹配改为
    _matches_term（ASCII 词按词边界，中文仍按子串），使 `ftp`/`pnl`/`krd`
    这类短词不再命中 `total_pnl` 之类更长的 token。词表顺序与既有守卫不变。
    """

    if not normalized_question:
        return ()
    hits: list[str] = []
    for intent, keywords in _INTENT_PATTERNS:
        if any(_matches_term(normalized_question, keyword) for keyword in keywords):
            hits.append(intent)
            continue
        # 在 pnl_summary 原有优先级位置评估「收益(非收益率)」守卫，
        # 保持它先于 market_data、后于 product_pnl / pnl_bridge 的既有顺序。
        if intent == "pnl_summary" and _CHINESE_PNL_RETURN_PATTERN.search(normalized_question):
            hits.append(intent)
    if hits:
        return _apply_intent_specializations(tuple(hits))
    # 以下三条是「无词表命中」时的歧义词兜底，保持既有单一结果语义。
    if _matches_domain_combination(
        normalized_question,
        ambiguous_terms=_GITNEXUS_AMBIGUOUS_TERMS,
        domain_terms=_GITNEXUS_DOMAIN_TERMS,
    ):
        return ("gitnexus_status",)
    if "duration" in normalized_question and (
        _matches_any(normalized_question, _DURATION_DOMAIN_TERMS)
        or _page_default_intent(request) == "duration_risk"
    ):
        return ("duration_risk",)
    if "market value" in normalized_question and (
        _matches_any(normalized_question, _MARKET_VALUE_DOMAIN_TERMS)
        or _page_default_intent(request) == "portfolio_overview"
    ):
        return ("portfolio_overview",)
    return ()


def _apply_intent_specializations(hits: tuple[str, ...]) -> tuple[str, ...]:
    suppressed: set[str] = set()
    for intent in hits:
        suppressed.update(_INTENT_SPECIALIZATIONS.get(intent, frozenset()))
    return tuple(intent for intent in hits if intent not in suppressed)


def _keyword_intent_resolution(
    request: AgentQueryRequest,
    normalized_question: str,
) -> LocalRequestResolution | None:
    candidates = _intent_candidates_from_question(normalized_question, request=request)
    if not candidates:
        return None

    kept = tuple(
        intent
        for intent in candidates
        if not _is_negated_intent(normalized_question, intent)
    )
    if not kept:
        return _intent_clarification(
            reason_code="negated_intent_reference",
            intent_candidates=candidates,
        )
    candidates = kept

    if len({_INTENT_FAMILIES.get(intent, intent) for intent in candidates}) > 1:
        # 显式 intent / workflow 已在更早的优先级返回；此处只剩页面默认可消歧。
        page_intent = _page_default_intent(request)
        if page_intent in candidates:
            candidates = (page_intent,)
        else:
            return _intent_clarification(
                reason_code="multiple_intents",
                intent_candidates=candidates,
            )

    intent = candidates[0]
    if _requires_explicit_report_date(request, normalized_question, intent):
        return _intent_clarification(
            reason_code="relative_date_requires_explicit_report_date",
            intent_candidates=(intent,),
        )
    return LocalRequestResolution(
        route="local",
        reason="governed_keyword",
        intent=intent,
    )


def _intent_clarification(
    *,
    reason_code: str,
    intent_candidates: tuple[str, ...],
) -> LocalRequestResolution:
    """复用既有 clarification_required 机制承载关键词路由层的澄清。

    语义快照的 intent 词表只接受 ontology_clarification，故沿用该 intent；
    真正的候选业务 intent 放在 intent_candidates 上。
    """

    return LocalRequestResolution(
        route="local",
        reason="intent_clarification",
        intent="ontology_clarification",
        semantic_status="clarification_required",
        semantic_reason_code=reason_code,
        intent_candidates=intent_candidates,
    )


def _is_negated_intent(normalized_question: str, intent: str) -> bool:
    """intent 的每一处关键词命中都落在否定小句里时，视为被否定。"""

    matched = False
    for keyword in _intent_keywords(intent):
        for start in _term_match_positions(normalized_question, keyword):
            matched = True
            if not _is_negated_clause_prefix(normalized_question, start):
                return False
    if intent == "pnl_summary":
        for match in _CHINESE_PNL_RETURN_PATTERN.finditer(normalized_question):
            matched = True
            if not _is_negated_clause_prefix(normalized_question, match.start()):
                return False
    return matched


def _intent_keywords(intent: str) -> tuple[str, ...]:
    for candidate_intent, keywords in _INTENT_PATTERNS:
        if candidate_intent == intent:
            return keywords
    return ()


def _term_match_positions(normalized_question: str, term: str) -> list[int]:
    pattern = (
        rf"(?<!\w){re.escape(term)}(?!\w)" if term.isascii() else re.escape(term)
    )
    return [match.start() for match in re.finditer(pattern, normalized_question)]


def _is_negated_clause_prefix(normalized_question: str, start: int) -> bool:
    clause_start = max(
        (normalized_question.rfind(separator, 0, start) for separator in "，,；;。.!！？?\n"),
        default=-1,
    )
    prefix = normalized_question[clause_start + 1 : start]
    return any(pattern.search(prefix) for pattern in _INTENT_NEGATION_PATTERNS)


def _requires_explicit_report_date(
    request: AgentQueryRequest,
    normalized_question: str,
    intent: str,
) -> bool:
    """相对「日」问法 + 无任何显式报告日时，报告日绑定型意图不得静默取 latest。"""

    if intent not in _REPORT_DATE_BOUND_INTENTS:
        return False
    if not any(pattern.search(normalized_question) for pattern in _RELATIVE_DAY_PATTERNS):
        return False
    return not _has_explicit_report_date_reference(request, normalized_question)


def _has_explicit_report_date_reference(
    request: AgentQueryRequest,
    normalized_question: str,
) -> bool:
    containers: list[dict[str, Any]] = [request.filters, request.context]
    current_filters = request.context.get("current_filters")
    if isinstance(current_filters, dict):
        containers.append(current_filters)
    if request.page_context is not None:
        containers.append(request.page_context.current_filters)
    for container in containers:
        for key in ("report_date", "date"):
            value = container.get(key)
            if value is not None and str(value).strip():
                return True
    return _ISO_DATE_PATTERN.search(normalized_question) is not None


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
