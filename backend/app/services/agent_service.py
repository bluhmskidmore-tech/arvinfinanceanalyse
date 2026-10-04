from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from backend.app.agent.runtime.local_request_resolution import (
    SEMANTIC_EXECUTION_CONTEXT_KEY,
    LocalRequestResolution,
    _semantic_report_date,
    ontology_request_scope_errors,
    resolve_local_request,
    validate_semantic_execution_request,
)
from backend.app.agent.runtime.ontology_bindings import (
    ONTOLOGY_BINDING_REVISION,
    OntologyMetricBinding,
    get_bound_metric_entity,
    get_ontology_metric_binding,
    ontology_content_revision,
    ontology_reference_payload,
)
from backend.app.agent.runtime.tool_registry import ToolRegistry
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.core_finance.field_normalization import normalize_currency_basis_value
from backend.app.governance.agent_audit import AgentAuditPayload, append_agent_audit
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.choice_news_repo import (
    choice_news_filters,
    choice_news_latest_events_sql,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.product_category_pnl_repo import (
    PRODUCT_CATEGORY_PNL_ROWS_SQL,
    ProductCategoryPnlRepository,
)
from backend.app.repositories.risk_tensor_repo import RiskTensorRepository
from backend.app.security.auth_context import AuthContext, ensure_user_allowed
from backend.app.services.dexter_research_context_builder import resolve_dexter_research_read_resources
from backend.app.services.explicit_numeric import is_numeric_json
from backend.app.services.gitnexus_service import build_gitnexus_status_payload
from backend.app.services.research_radar_service import research_radar_brief_payload

RULE_VERSION = "rv_agent_mvp_v1"
BalanceAnalysisRepository = None
_PORTFOLIO_AMOUNT_QUANTUM = Decimal("0.00000001")

# intent -> 该 intent 处理器实际读取的正式资源。资源名与对应 REST 路由的 read 授权保持一致
# （balance_analysis.py / pnl.py / risk_tensor.py / bond_analytics.py / product_category_pnl.py /
# macro_vendor.py / choice_news.py / pretrade_checklist.py / strategy_reports.py / cube_query.py），
# 使 agent 入口不能绕过这些路由各自的 read 权限。未列出的 intent（analysis_chat、gitnexus_status、
# 工作流 plan 卡、unknown）不读取受治理业务数据，仅受路由层 agent:read 约束。
INTENT_READ_RESOURCES: dict[str, str] = {
    "portfolio_overview": "balance_analysis",
    "pnl_summary": "pnl",
    "pnl_bridge": "pnl",
    "duration_risk": "risk_tensor",
    "risk_tensor": "risk_tensor",
    "credit_exposure": "bond_analytics",
    "product_pnl": "product_category_pnl",
    "market_data": "macro_vendor",
    "news": "choice_news.data",
    "research_radar_brief": "choice_news.data",
    "pretrade_checklist": "pretrade_checklist",
    "walk_forward_verdict": "strategy_reports",
    "cube_query": "cube",
}

# 仅用于证据披露（sql_executed）：与 repository 实际执行语句等价的只读 SELECT 模板，
# `?` 为参数占位符；实际绑定值见 evidence.filters_applied。服务端从不执行客户端传入 SQL。
_PORTFOLIO_OVERVIEW_SQL_DISCLOSURE = [
    (
        "select count(*) as detail_row_count, sum(market_value_amount) as total_market_value_amount, "
        "sum(amortized_cost_amount) as total_amortized_cost_amount, "
        "sum(accrued_interest_amount) as total_accrued_interest_amount "
        "from fact_formal_zqtz_balance_daily "
        "where report_date = ? and currency_basis = ? and (? = 'all' or position_scope = ?)"
    ),
    (
        "select count(*) as detail_row_count, sum(principal_amount) as total_market_value_amount, "
        "sum(principal_amount) as total_amortized_cost_amount, "
        "sum(accrued_interest_amount) as total_accrued_interest_amount "
        "from fact_formal_tyw_balance_daily "
        "where report_date = ? and currency_basis = ? and (? = 'all' or position_scope = ?)"
    ),
]
_PNL_SUMMARY_SQL_DISCLOSURE = [
    (
        "select count(*) as formal_fi_row_count, sum(interest_income_514), sum(fair_value_change_516), "
        "sum(capital_gain_517), sum(manual_adjustment), sum(total_pnl) "
        "from fact_formal_pnl_fi where report_date = ?"
    ),
    (
        "select count(*) as nonstd_bridge_row_count, sum(interest_income_514), sum(fair_value_change_516), "
        "sum(capital_gain_517), sum(manual_adjustment), sum(total_pnl) "
        "from fact_nonstd_pnl_bridge where report_date = ?"
    ),
]
_CREDIT_EXPOSURE_SQL_DISCLOSURE = [
    (
        "select instrument_code, market_value, is_credit, spread_dv01, accounting_class, rating "
        "from fact_formal_bond_analytics_daily where report_date = ? order by instrument_code"
    ),
    (
        "select instrument_code, market_value, is_credit, spread_dv01, accounting_class, rating "
        "from fact_formal_bond_analytics_daily where report_date = ? and asset_class_std = 'credit' "
        "order by instrument_code"
    ),
]
# product_pnl 披露与 ProductCategoryPnlRepository.fetch_rows 执行的是同一份常量。
_PRODUCT_PNL_SQL_DISCLOSURE = [PRODUCT_CATEGORY_PNL_ROWS_SQL]
# risk_tensor disclosure for the fully materialized v5 fact schema used by
# RiskTensorRepository.fetch_risk_tensor_row. Historical missing columns still
# fall back via repository null/coalesce handling; this list declares the
# canonical read-only projection.
_RISK_TENSOR_SQL_DISCLOSURE = [
    (
        "select report_date, portfolio_dv01, regulatory_dv01, krd_1y, krd_3y, krd_5y, krd_7y, "
        "krd_10y, krd_30y, cs01, portfolio_convexity, portfolio_modified_duration, "
        "rate_risk_market_value, rate_risk_dv01, rate_risk_modified_duration, "
        "duration_excluded_market_value, duration_excluded_count, "
        "missing_maturity_market_value, missing_maturity_count, "
        "floating_rate_proxy_market_value, floating_rate_proxy_count, "
        "payment_frequency_fallback_market_value, payment_frequency_fallback_count, "
        "bullet_value_date_fallback_market_value, bullet_value_date_fallback_count, "
        "issuer_concentration_hhi, "
        "issuer_top5_weight, asset_cashflow_30d, asset_cashflow_90d, liability_cashflow_30d, "
        "liability_cashflow_90d, liquidity_gap_30d, liquidity_gap_90d, liquidity_gap_30d_ratio, "
        "total_market_value, bond_count, quality_flag, warnings_json, source_version, "
        "upstream_source_version, upstream_rule_version, upstream_cache_version, "
        "liability_source_version, liability_rule_version, rule_version, cache_version, trace_id "
        "from fact_formal_risk_tensor_daily where report_date = ? limit 1"
    ),
]
# pnl_bridge 披露主干只读事实拉取（桥接本身在 core_finance 内存计算，不另写 SQL）。
_PNL_BRIDGE_SQL_DISCLOSURE = [
    (
        "select report_date, instrument_code, portfolio_name, cost_center, invest_type_std, "
        "accounting_basis, currency_basis, interest_income_514, fair_value_change_516, "
        "capital_gain_517, manual_adjustment, total_pnl, source_version, rule_version, "
        "ingest_batch_id, trace_id "
        "from fact_formal_pnl_fi where report_date = ?"
    ),
    (
        "select * from fact_formal_zqtz_balance_daily "
        "where report_date = ? and position_scope = 'asset' and currency_basis = 'CNY'"
    ),
]
# market_data 披露主干：macro 最近点 + formal FX mid（动态币种 in-list 见 filters_applied）。
_MARKET_DATA_SQL_DISCLOSURE = [
    (
        "with ranked as ( "
        "select series_id, series_name, trade_date, value_numeric, frequency, unit, "
        "source_version, vendor_version, quality_flag, "
        "row_number() over(partition by series_id order by trade_date desc) as rn "
        "from fact_choice_macro_daily "
        ") "
        "select series_id, series_name, trade_date, value_numeric, frequency, unit, "
        "source_version, vendor_version, quality_flag, rn "
        "from ranked where rn <= 20 order by series_id, rn"
    ),
    (
        "with ranked as ( "
        "select base_currency, quote_currency, cast(trade_date as varchar) as trade_date, "
        "cast(observed_trade_date as varchar) as observed_trade_date, "
        "cast(mid_rate as double) as mid_rate, source_name, "
        "coalesce(vendor_name, '') as vendor_name, coalesce(vendor_version, '') as vendor_version, "
        "source_version, is_business_day, is_carry_forward, "
        "row_number() over (partition by upper(base_currency), upper(quote_currency) "
        "order by trade_date desc) as rn "
        "from fx_daily_mid "
        "where upper(quote_currency) = 'CNY' "
        ") "
        "select base_currency, quote_currency, trade_date, observed_trade_date, mid_rate, "
        "source_name, vendor_name, vendor_version, source_version, is_business_day, "
        "is_carry_forward from ranked where rn = 1"
    ),
]


# news 披露主干：静态 SQL 模板部分（与 choice_news_repo 执行链路同源渲染，
# `{where_clause}` 为唯一运行期槽位）。运行期由同源 choice_news_filters 按本次
# 过滤条件填充 where 子句，过滤值一律保持 `?` 绑定占位，仅披露不执行。
# 常量名 `_NEWS_SQL_DISCLOSURE` 是与 Eval 静态 drift 护栏的双方契约，勿改名。
_NEWS_SQL_DISCLOSURE: list[str] = [
    " ".join(
        choice_news_latest_events_sql(
            where_clause="{where_clause}",
            include_payload_json=True,
        ).split()
    ),
]


# pretrade_checklist 披露主干只读拉取：候选历史 + 观测行情 + 涨跌停价 + 复权因子
# （与 pretrade_checklist_service 的执行语句同构）。amount 列运行期由
# docs/data_contracts.md §4.10 的 amount_rmb_sql 归一为人民币元（缺 vendor_version
# 定标时降级 cast(null as double)）；`stock_code in (?)` 的占位符数量运行期按候选
# 代码数展开；门控敞口轻读（core_finance.gate_exposure_series）不在此展开。
_PRETRADE_CHECKLIST_SQL_DISCLOSURE = [
    "select max(snapshot_as_of_date) from livermore_candidate_history where signal_kind = ?",
    (
        "select candidate_rank, stock_code, stock_name, sector_name, selection_close, ema10, "
        "market_state, data_status, closed_up_limit "
        "from livermore_candidate_history "
        "where snapshot_as_of_date = ? and signal_kind = ? "
        "order by candidate_rank nulls last, stock_code"
    ),
    (
        "select stock_code, close_value, amount, tradestatus, highlimit, lowlimit "
        "from choice_stock_daily_observation "
        "where trade_date = ? and stock_code in (?)"
    ),
    (
        "select stock_code, up_limit, down_limit "
        "from stock_limit_price_daily "
        "where trade_date = ? and stock_code in (?)"
    ),
    (
        "select distinct stock_code "
        "from stock_adjustment_factor "
        "where trade_date = ? and stock_code in (?) and adj_factor is not null"
    ),
]

# 盘前清单可买状态与拦截原因的展示标签；未知代码回退原值，不吞信息。
_PRETRADE_STATUS_LABELS = {
    "buyable": "可买",
    "blocked_suspended": "停牌拦截",
    "blocked_limit": "涨跌停拦截",
    "review": "需复核",
    "data_missing": "数据缺失",
}
_PRETRADE_BLOCK_REASON_LABELS = {
    "suspended": "停牌",
    "limit_up": "涨停",
    "limit_down": "跌停",
    "missing_daily_observation": "缺当日观测行情",
    "missing_amount": "成交额缺失",
    "non_positive_amount": "成交额非正",
    "low_liquidity": "流动性低于门槛",
}

# walk_forward_verdict 判定标签与 strategy_report_service 的 verdict 契约对齐。
_WALK_FORWARD_VERDICT_LABELS = {
    "oos_supported": "样本外支持",
    "oos_weakened": "样本外衰减",
    "insufficient_windows": "样本不足",
}


def phase1_disabled_response() -> AgentDisabledResponse:
    return AgentDisabledResponse()


def execute_agent_query(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> AgentEnvelope:
    registry = ToolRegistry(
        duckdb_path,
        governance_dir,
        intent_handlers=_build_intent_handlers(duckdb_path, governance_dir),
    )
    try:
        envelope = registry.execute_query(request)
    except Exception as exc:
        # 合规底线：失败的查询同样必须留下审计痕迹，审计后原样上抛。
        _append_failed_query_audit(request, governance_dir, error=exc)
        raise
    _append_envelope_audit(request, governance_dir, envelope)
    return envelope


def resolve_agent_intent_read_resources(
    request: AgentQueryRequest,
    *,
    provider: str = "local",
) -> list[str]:
    """按 AnalysisViewTool.execute 的分派规则，列出本次请求将实际读取的正式资源。

    与执行链路同源使用 resolve_local_request：provider 路由不经本地 intent 处理器；
    金融工作流仅在 workflow_mode=execute 时逐个执行 mapped_intents（plan 卡不读数据）；
    研究工作流在 execute 模式或显式 context.intent 命中时执行其处理器。
    """
    resolution = resolve_local_request(request)
    if resolution.route != "local":
        if provider == "dexter":
            return resolve_dexter_research_read_resources(request)
        return []
    workflow_mode = str(request.context.get("workflow_mode") or "").strip().lower()
    intents: list[str] = []
    if resolution.financial_workflow is not None:
        if workflow_mode == "execute":
            intents.extend(resolution.financial_workflow.mapped_intents)
    elif resolution.research_workflow is not None:
        explicit_intent = (
            str(request.context.get("intent") or "").strip().lower().replace("-", "_")
        )
        if workflow_mode == "execute" or explicit_intent == resolution.research_workflow.workflow_id:
            intents.append(resolution.research_workflow.workflow_id)
    elif resolution.intent:
        intents.append(resolution.intent)
    resources: list[str] = []
    for intent in intents:
        resource = INTENT_READ_RESOURCES.get(intent)
        if resource is not None and resource not in resources:
            resources.append(resource)
    return resources


def ensure_agent_intent_resources_allowed(
    request: AgentQueryRequest,
    *,
    auth: AuthContext,
    settings: Any,
    authorize: Callable[..., None] = ensure_user_allowed,
    provider: str | None = None,
) -> None:
    """S-H2：agent:read 仅授权使用 Agent 入口；intent 实际读取的业务资源按其正式路由的 read 权限再校验。

    PermissionError / RuntimeError 原样上抛，由路由层映射为 403 / 503。``authorize`` 允许
    路由层传入自身命名空间的 ensure_user_allowed，以便测试替身仍能拦截（同 deps.ensure_read_allowed）。
    """
    resolved_provider = str(provider or getattr(settings, "agent_provider", "local")).strip().lower()
    for resource in resolve_agent_intent_read_resources(request, provider=resolved_provider):
        authorize(auth=auth, settings=settings, resource=resource, action="read")


def ensure_agent_execution_resources_allowed(
    request: AgentQueryRequest,
    *,
    settings: Any,
    resources: list[str],
) -> None:
    """Recheck reads against the server-bound identity before provider/recovery execution.

    HTTP entrypoints replace these identity fields; queued runs retain that request.
    A provider invoked without a server-bound user may chat, but cannot read business data.
    """
    if not resources:
        return
    user_id = str(request.context.get("user_id") or "").strip()
    if not user_id:
        raise PermissionError("Agent business reads require a server-bound user.")
    auth = AuthContext(
        user_id=user_id,
        role=str(request.context.get("user_role") or "viewer").strip(),
        identity_source=str(request.context.get("identity_source") or "fallback"),
    )
    for resource in resources:
        ensure_user_allowed(auth=auth, settings=settings, resource=resource, action="read")


def audit_disabled_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
) -> None:
    trace_id = f"tr_agent_disabled_{uuid4().hex[:12]}"
    _append_audit(
        request=request,
        governance_dir=governance_dir,
        trace_id=trace_id,
        tools_used=["agent_disabled"],
        tables_used=[],
        filters_applied={
            key: value
            for key, value in request.filters.items()
            if _audit_filter_value_present(value)
        },
        result_meta={
            "trace_id": trace_id,
            "basis": request.basis,
            "result_kind": "agent.disabled",
            "formal_use_allowed": False,
            "source_version": "sv_agent_disabled",
            "vendor_version": "vv_none",
            "rule_version": RULE_VERSION,
            "cache_version": "cv_agent_disabled_v1",
            "quality_flag": "warning",
            "scenario_flag": False,
        },
    )


def _build_intent_handlers(
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Callable[[AgentQueryRequest], dict[str, Any]]]:
    return {
        # gitnexus_status 非 DuckDB 查询（读 GitNexus 索引/MCP），sql_executed 保持 []。
        "gitnexus_status": lambda request: build_gitnexus_status_payload(request),
        "research_radar_brief": lambda request: research_radar_brief_payload(request, duckdb_path),
        "portfolio_overview": lambda request: _portfolio_overview_payload(
            request,
            duckdb_path,
            governance_dir,
        ),
        "pnl_summary": lambda request: _pnl_summary_payload(
            request,
            duckdb_path,
            governance_dir,
        ),
        "duration_risk": lambda request: _duration_risk_payload(
            request,
            duckdb_path,
            governance_dir,
        ),
        "credit_exposure": lambda request: _credit_exposure_payload(
            request,
            duckdb_path,
            governance_dir,
        ),
        "product_pnl": lambda request: _product_pnl_payload(request, duckdb_path),
        "pnl_bridge": lambda request: _pnl_bridge_payload(request, duckdb_path, governance_dir),
        "risk_tensor": lambda request: _risk_tensor_payload(request, duckdb_path, governance_dir),
        "market_data": lambda request: _market_data_payload(request, duckdb_path),
        "news": lambda request: _news_payload(request, duckdb_path),
        "pretrade_checklist": lambda request: _pretrade_checklist_payload(request, duckdb_path),
        # walk_forward_verdict 读取落盘 JSON 报告（strategy_report_service），不触 DuckDB。
        "walk_forward_verdict": lambda request: _walk_forward_verdict_payload(request),
    }


# Agent payload 可以从上游正式 envelope 的 result_meta 继承的字段白名单。
# 治理版本串每个都必须有 handler 提供的缺省值；上下文字段只有沿用上游日期/金额口径的
# handler 才继承；可选字段仅在上游存在时透传。禁止直接合并整个上游 result_meta：
# 那会把上游新增字段无审查地带进 Agent 契约。
_UPSTREAM_META_GOVERNANCE_FIELDS: tuple[str, ...] = (
    "basis",
    "source_version",
    "vendor_version",
    "rule_version",
    "cache_version",
    "vendor_status",
    "fallback_mode",
)
_UPSTREAM_META_CONTEXT_FIELDS: tuple[str, ...] = (
    "requested_report_date",
    "resolved_report_date",
    "as_of_date",
    "date_basis",
    "fallback_date",
    "source_surface",
    "amount_currency_basis",
    "amount_currency_basis_note",
    "generated_at",
)
_UPSTREAM_META_PASSTHROUGH_FIELDS: tuple[str, ...] = (
    "cache_key",
    "data_built_at",
)


def _upstream_meta_projection(
    meta: Mapping[str, Any],
    *,
    agent_formal_gate: bool,
    governance_defaults: Mapping[str, str],
    inherit_context: bool = False,
    context_defaults: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """按白名单把上游正式 envelope 的 result_meta 投影为 Agent payload 的 meta 字段。

    ``agent_formal_gate`` 是 handler 自身的 fail-closed 判定，正式口径取它与上游
    ``formal_use_allowed`` 的合取，所以上游为 false 时 Agent 不可能升级为 true。
    ``quality_flag`` 不在白名单内：各 handler 的降级规则不同，仍由 handler 自行判定。
    """
    projected: dict[str, Any] = {
        "formal_use_allowed": (
            bool(meta.get("formal_use_allowed", False)) and bool(agent_formal_gate)
        ),
        "scenario_flag": bool(meta.get("scenario_flag", False)),
    }
    for field_name in _UPSTREAM_META_GOVERNANCE_FIELDS:
        projected[field_name] = str(meta.get(field_name) or governance_defaults[field_name])
    if inherit_context:
        defaults = context_defaults or {}
        for field_name in _UPSTREAM_META_CONTEXT_FIELDS:
            projected[field_name] = meta.get(field_name) or defaults.get(field_name)
    for field_name in _UPSTREAM_META_PASSTHROUGH_FIELDS:
        value = meta.get(field_name)
        if value is not None:
            projected[field_name] = value
    return projected


def _portfolio_overview_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    from backend.app.services.balance_analysis_service import balance_analysis_overview_envelope

    repo_cls = BalanceAnalysisRepository
    if repo_cls is None:
        balance_analysis_repo_module = importlib.import_module("backend.app.repositories.balance_analysis_repo")
        repo_cls = balance_analysis_repo_module.BalanceAnalysisRepository
    repo = repo_cls(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No balance-analysis report date is available.")
    currency_basis = _balance_analysis_currency_basis(request)
    # The balance service retains responsibility for rejecting invalid filters.
    upstream = balance_analysis_overview_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
        position_scope=cast(Literal["asset", "liability", "all"], request.position_scope),
        currency_basis=cast(Literal["native", "CNY"], currency_basis),
    )
    overview = dict(cast(Mapping[str, Any], upstream.get("result") or {}))
    meta = dict(cast(Mapping[str, Any], upstream.get("result_meta") or {}))
    lineage_overview = repo.fetch_formal_overview(
        report_date=report_date,
        position_scope=request.position_scope,
        currency_basis=currency_basis,
    )
    detail_row_count = int(overview["detail_row_count"])
    lineage_row_count = int(lineage_overview.get("lineage_row_count") or detail_row_count or 0)
    source_version_missing_count = int(lineage_overview.get("source_version_missing_count") or 0)
    rule_version_missing_count = int(lineage_overview.get("rule_version_missing_count") or 0)
    requested_report_date = _requested_report_date(request)
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if requested_report_date else "latest_default"
    )
    cny_amount_contract = currency_basis == "CNY"
    lineage_complete = (
        lineage_row_count > 0
        and source_version_missing_count == 0
        and rule_version_missing_count == 0
    )
    formal_use_allowed = detail_row_count > 0 and cny_amount_contract and lineage_complete
    upstream_quality = str(meta.get("quality_flag") or "warning")
    quality_flag: Literal["ok", "warning"] = "ok" if formal_use_allowed else "warning"
    if upstream_quality in {"error", "stale"}:
        quality_flag = "warning"

    if detail_row_count <= 0:
        answer = (
            f"{report_date} 在 position_scope={request.position_scope}、"
            f"currency_basis={currency_basis} 下没有受治理的组合明细，未生成金融金额。"
        )
        cards = [
            {
                "type": "status",
                "title": "No Governed Portfolio Data",
                "value": "当前筛选条件没有可用于正式展示的组合记录。",
            }
        ]
    elif not cny_amount_contract:
        answer = (
            f"{report_date} 的组合记录已返回，但 currency_basis={currency_basis} "
            "不具备单一人民币金额单位，未生成金额型指标卡。"
        )
        cards = [
            {
                "type": "status",
                "title": "Currency Unit Requires Review",
                "value": "原币口径可能包含多币种，不能标记为 yuan 或作为正式汇总金额。",
            }
        ]
    elif not lineage_complete:
        missing_lineage_parts = []
        if source_version_missing_count > 0:
            missing_lineage_parts.append("source_version")
        if rule_version_missing_count > 0:
            missing_lineage_parts.append("rule_version")
        missing_lineage_text = ", ".join(missing_lineage_parts)
        answer = (
            f"{report_date} 的组合记录已返回，但 Agent 侧行级受治理 lineage 缺少 {missing_lineage_text}；"
            "系统已按 Agent 附加检查 fail-closed，未生成正式金额或 Numeric 指标。"
        )
        cards = [
            {
                "type": "status",
                "title": "Governed Lineage Incomplete",
                "value": (
                    "Formal portfolio amount cards were suppressed because governed "
                    f"row-level lineage is missing {missing_lineage_text} in the Agent-side check."
                ),
            }
        ]
    else:
        scope_amount_label = {
            "asset": "资产市值",
            "liability": "负债市值",
            "all": "资产与负债市值毛额",
        }.get(request.position_scope, "组合市值")
        cards = [
            _portfolio_amount_card(
                title="Total Market Value",
                metric_id="MTR-BAL-001",
                source_field="total_market_value_amount",
                value=overview["total_market_value_amount"],
            ),
            _portfolio_amount_card(
                title="Total Amortized Cost",
                metric_id="MTR-BAL-002",
                source_field="total_amortized_cost_amount",
                value=overview["total_amortized_cost_amount"],
            ),
            _portfolio_amount_card(
                title="Total Accrued Interest",
                metric_id="MTR-BAL-003",
                source_field="total_accrued_interest_amount",
                value=overview["total_accrued_interest_amount"],
            ),
            _portfolio_count_card(
                title="Detail Rows",
                metric_id="MTR-BAL-101",
                source_field="detail_row_count",
                value=detail_row_count,
            ),
        ]
        answer = (
            f"{report_date} 的组合概览已返回，当前口径共 {detail_row_count} 条明细，"
            f"{scope_amount_label} {cards[0]['value']}。"
        )

    return {
        "answer": answer,
        "cards": cards,
        "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
        "filters_applied": _audit_filters(
            request,
            report_date,
            resolution=rd_mode,
            extra={
                "position_scope": request.position_scope,
                "currency_basis": currency_basis,
            },
        ),
        "row_count": detail_row_count,
        "sql_executed": _PORTFOLIO_OVERVIEW_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_balance_analysis_unavailable",
                "vendor_version": "vv_none",
                "rule_version": "rv_balance_analysis_unavailable",
                "cache_version": "cv_agent_portfolio_overview_v1",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            inherit_context=True,
            context_defaults={
                "requested_report_date": (
                    _coerce_iso_report_date(requested_report_date)
                    if requested_report_date is not None
                    else None
                ),
                "resolved_report_date": report_date,
                "as_of_date": report_date,
                "date_basis": "balance_analysis_report_date",
                "fallback_date": None,
                "source_surface": "formal_balance",
                "amount_currency_basis": currency_basis,
            },
        ),
        "result_kind": "agent.portfolio_overview",
        "amount_currency_basis": currency_basis,
        "amount_currency_basis_note": (
            "原币口径可能包含多币种，未生成金额型 Numeric 卡片。"
            if not cny_amount_contract
            else "Agent 侧行级治理 lineage 缺少 source_version 或 rule_version，已抑制正式金额型 Numeric 卡片。"
            if not lineage_complete
            else "金额卡沿用正式 Balance Analysis 原始单位 yuan，未做前端换算。"
        ),
        "next_drill": [
            {"dimension": "portfolio", "label": "按组合查看"},
            {"dimension": "cost_center", "label": "按成本中心查看"},
        ],
        "suggested_actions": [
            {
                "type": "inspect_lineage",
                "label": "查看组合概览来源",
                "payload": {"metric_key": "portfolio_overview", "report_date": report_date},
            },
            {
                "type": "inspect_drill",
                "label": "按组合查看",
                "payload": {"dimension": "portfolio", "report_date": report_date},
            },
        ],
    }


def _balance_analysis_currency_basis(request: AgentQueryRequest) -> str:
    raw_currency_basis = str(request.currency_basis or "CNY").strip()
    if raw_currency_basis.lower() == "native":
        return "native"
    currency_basis = raw_currency_basis.upper()
    if currency_basis == "CNX":
        return "CNY"
    return currency_basis or "CNY"


def _portfolio_amount_card(
    *,
    title: str,
    metric_id: str,
    source_field: str,
    value: Any,
) -> dict[str, Any]:
    if value is None:
        return {
            "type": "metric",
            "title": title,
            "value": "—",
            "spec": {
                "metric_id": metric_id,
                "source_field": source_field,
                "raw_value": None,
                "raw_unit": "yuan",
                "raw_precision": 8,
                "numeric": {
                    "raw": None,
                    "unit": "yuan",
                    "display": "—",
                    "precision": 8,
                    "sign_aware": False,
                },
            },
        }
    raw_decimal = Decimal(str(value)).quantize(
        _PORTFOLIO_AMOUNT_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    raw_value = format(raw_decimal, ".8f")
    display = f"{raw_decimal:,.8f} 元"
    return {
        "type": "metric",
        "title": title,
        "value": display,
        "spec": {
            "metric_id": metric_id,
            "source_field": source_field,
            "raw_value": raw_value,
            "raw_unit": "yuan",
            "raw_precision": 8,
            "numeric": {
                "raw": float(raw_decimal),
                "unit": "yuan",
                "display": display,
                "precision": 8,
                "sign_aware": False,
            },
        },
    }


def _portfolio_count_card(
    *,
    title: str,
    metric_id: str,
    source_field: str,
    value: int,
) -> dict[str, Any]:
    display = f"{value:,}"
    return {
        "type": "metric",
        "title": title,
        "value": display,
        "spec": {
            "metric_id": metric_id,
            "source_field": source_field,
            "raw_value": str(value),
            "raw_unit": "count",
            "raw_precision": 0,
            "numeric": {
                "raw": value,
                "unit": "count",
                "display": display,
                "precision": 0,
                "sign_aware": False,
            },
        },
    }


def _pnl_summary_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    from backend.app.services.pnl_service import pnl_overview_envelope

    resolution = resolve_local_request(request)
    repo = PnlRepository(duckdb_path)
    report_date = resolution.report_date or _latest_or_requested(
        request, repo.list_union_report_dates()
    )
    if report_date is None:
        raise ValueError("No PnL report date is available.")
    upstream = pnl_overview_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
    )
    overview = dict(cast(Mapping[str, Any], upstream.get("result") or {}))
    meta = dict(cast(Mapping[str, Any], upstream.get("result_meta") or {}))
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit"
        if resolution.report_date or _requested_report_date(request)
        else "latest_default"
    )
    formal_fi_row_count = int(overview.get("formal_fi_row_count") or 0)
    nonstd_bridge_row_count = int(overview.get("nonstd_bridge_row_count") or 0)
    # fail-closed：没有正式 FI 明细时（仅剩非标桥接行），不得宣称正式口径。
    formal_use_allowed = bool(meta.get("formal_use_allowed", False)) and formal_fi_row_count > 0
    upstream_quality = str(meta.get("quality_flag") or "warning")
    quality_flag = (
        upstream_quality
        if upstream_quality in {"error", "stale"}
        else "ok"
        if upstream_quality == "ok" and formal_use_allowed
        else "warning"
    )

    binding = (
        get_ontology_metric_binding(resolution.metric_id)
        if resolution.semantic_operation == "value"
        else None
    )
    binding_block_reason = (
        _pnl_ontology_binding_block_reason(
            binding=binding,
            overview=overview,
            meta=meta,
            report_date=report_date,
            formal_fi_row_count=formal_fi_row_count,
            request=request,
        )
        if binding is not None
        else None
    )
    if binding is not None and binding_block_reason is None:
        metric_entity = get_bound_metric_entity(binding.metric_id)
        assert metric_entity is not None
        metric_value = overview[binding.result_field]
        cards = [
            _pnl_metric_card(
                title=metric_entity.name,
                metric_id=binding.metric_id,
                source_field=binding.result_field,
                value=metric_value,
                unit=metric_entity.unit or "yuan",
                precision=metric_entity.precision if metric_entity.precision is not None else 2,
            )
        ]
        answer = (
            f"{report_date} 的{metric_entity.name}为 {_pnl_metric_display(metric_value, metric_entity.precision or 2)}。"
        )
        semantic_context: dict[str, Any] | None = _pnl_semantic_context(
            resolution=resolution,
            meta=meta,
            result_check="matched",
            reason_code="metric_value_resolved",
        )
    elif binding is not None:
        formal_use_allowed = False
        if quality_flag == "ok":
            quality_flag = "warning"
        upstream_diagnostics = _pnl_upstream_block_diagnostics(overview)
        cards = [
            {
                "type": "status",
                "title": "Metric Result Blocked",
                "value": (
                    "正式 overview 返回与已核对指标绑定不一致，系统未展示该指标数值。"
                ),
                "metric_id": binding.metric_id,
                "data": {
                    "reason_code": binding_block_reason,
                    "upstream_diagnostics": upstream_diagnostics,
                },
            }
        ]
        answer = (
            f"{report_date} 的指标结果未通过绑定检查（{binding_block_reason}），"
            "系统未将上游事实值标记为该指标答案。"
        )
        if upstream_diagnostics:
            answer += f"上游降级原因：{'；'.join(upstream_diagnostics)}。"
        semantic_context = _pnl_semantic_context(
            resolution=resolution,
            meta=meta,
            result_check="blocked",
            reason_code=cast(str, binding_block_reason),
        )
    else:
        cards = [
            {"type": "metric", "title": "Total PnL", "value": str(overview.get("total_pnl"))},
            {
                "type": "metric",
                "title": "Interest 514",
                "value": str(overview.get("interest_income_514")),
            },
            {
                "type": "metric",
                "title": "Fair Value 516",
                "value": str(overview.get("fair_value_change_516")),
            },
            {
                "type": "metric",
                "title": "Capital Gain 517",
                "value": str(overview.get("capital_gain_517")),
            },
        ]
        answer = (
            f"{report_date} 的损益汇总已返回，正式 FI {formal_fi_row_count} 行，"
            f"非标桥接 {nonstd_bridge_row_count} 行，总损益 {overview.get('total_pnl')}。"
        )
        semantic_context = None
    if not formal_use_allowed:
        if formal_fi_row_count <= 0:
            answer += (
                "当前日期没有正式 FI 明细，汇总仅由非标桥接数据构成；"
                "系统已 fail-closed，本结果按非正式口径返回（formal_use_allowed=false）。"
            )
        else:
            answer += "上游正式服务不允许本结果正式使用（formal_use_allowed=false）。"

    pnl_filter_disclosure = (
        {
            "requested_position_scope": request.position_scope,
            "requested_currency_basis": request.currency_basis,
        }
        if binding is not None
        else {
            "position_scope": request.position_scope,
            "currency_basis": request.currency_basis,
        }
    )
    payload: dict[str, Any] = {
        "answer": answer,
        "cards": cards,
        "tables_used": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
        "filters_applied": _audit_filters(
            request,
            report_date,
            resolution=rd_mode,
            extra=pnl_filter_disclosure,
        ),
        "row_count": formal_fi_row_count + nonstd_bridge_row_count,
        "sql_executed": _PNL_SUMMARY_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_pnl_overview_missing",
                "vendor_version": "vv_none",
                "rule_version": RULE_VERSION,
                "cache_version": "cv_pnl_overview_missing",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            inherit_context=True,
            context_defaults={
                "requested_report_date": report_date,
                "resolved_report_date": report_date,
                "as_of_date": report_date,
            },
        ),
        # 保留既有 Agent 消费契约；上游 kind/trace 写入 semantic_context。
        "result_kind": "agent.pnl_summary",
        "next_drill": (
            [
                {"dimension": "instrument", "label": "按券查看"},
                {"dimension": "portfolio", "label": "按组合查看"},
            ]
            if resolution.semantic_operation != "value"
            else []
        ),
        "suggested_actions": (
            [
                {
                    "type": "inspect_lineage",
                    "label": "查看损益来源",
                    "payload": {"metric_key": "total_pnl", "report_date": report_date},
                },
                {
                    "type": "inspect_drill",
                    "label": "查看PnL桥接",
                    "payload": {"intent": "pnl_bridge", "report_date": report_date},
                },
            ]
            if resolution.semantic_operation != "value"
            else []
        ),
    }
    if semantic_context is not None:
        payload["semantic_context"] = semantic_context
    return payload


def _pnl_ontology_binding_block_reason(
    *,
    binding: OntologyMetricBinding | None,
    overview: dict[str, Any],
    meta: dict[str, Any],
    report_date: str,
    formal_fi_row_count: int,
    request: AgentQueryRequest,
) -> str | None:
    if binding is None or get_bound_metric_entity(binding.metric_id) is None:
        return "metric_binding_unavailable"
    if str(overview.get("report_date") or "") != report_date:
        return "result_report_date_mismatch"
    if str(meta.get("requested_report_date") or "") != report_date:
        return "requested_report_date_mismatch"
    if str(meta.get("resolved_report_date") or "") != report_date:
        return "resolved_report_date_mismatch"
    if str(meta.get("basis") or "") != "formal":
        return "upstream_basis_mismatch"
    if str(meta.get("source_surface") or "") != "formal_pnl":
        return "upstream_source_surface_mismatch"
    if str(meta.get("result_kind") or "") != binding.upstream_result_kind:
        return "upstream_result_kind_mismatch"
    if str(meta.get("fallback_mode") or "") != "none":
        return "upstream_fallback_not_allowed"
    if ontology_request_scope_errors(request):
        return "request_scope_not_supported"
    upstream_currency_basis = str(meta.get("amount_currency_basis") or "").strip()
    if not upstream_currency_basis:
        return "upstream_amount_currency_basis_missing"
    try:
        normalized_upstream_currency = normalize_currency_basis_value(
            upstream_currency_basis
        )
        normalized_request_currency = normalize_currency_basis_value(
            request.currency_basis
        )
    except ValueError:
        return "upstream_amount_currency_basis_mismatch"
    if normalized_upstream_currency != normalized_request_currency:
        return "upstream_amount_currency_basis_mismatch"
    if "formal_use_allowed" not in meta:
        return "upstream_formal_use_marker_missing"
    if meta.get("formal_use_allowed") is not True:
        return "upstream_formal_use_not_allowed"
    for field_name in ("trace_id", "source_version", "rule_version", "cache_version"):
        if not str(meta.get(field_name) or "").strip():
            return f"upstream_{field_name}_missing"
    if binding.result_field not in overview or overview.get(binding.result_field) is None:
        return "metric_value_missing"
    if formal_fi_row_count <= 0:
        return "formal_fi_source_missing"
    return None


def _pnl_upstream_block_diagnostics(overview: dict[str, Any]) -> list[str]:
    checks = overview.get("reconciliation_checks")
    if not isinstance(checks, dict):
        return []
    diagnostics: list[str] = []
    for check_name, raw_check in checks.items():
        if not isinstance(raw_check, dict):
            continue
        status = str(raw_check.get("status") or "").strip().lower()
        breached = raw_check.get("breached") is True
        reason = str(raw_check.get("reason") or "").strip()
        if not breached and status not in {"fail", "failed", "error", "stale"} and not reason:
            continue
        label = str(raw_check.get("check_kind") or check_name).strip()
        state = status or ("breached" if breached else "warning")
        detail = f"{label}:{state}"
        if reason:
            detail += f"（{reason[:240]}）"
        diagnostics.append(detail)
    return diagnostics


def _pnl_semantic_context(
    *,
    resolution: LocalRequestResolution,
    meta: dict[str, Any],
    result_check: Literal["matched", "blocked"],
    reason_code: str,
) -> dict[str, Any]:
    assert resolution.metric_id is not None
    return {
        "status": "resolved",
        "result_check": result_check,
        "references": [ontology_reference_payload(resolution.metric_id)],
        "ontology_revision": ontology_content_revision(),
        "binding_revision": ONTOLOGY_BINDING_REVISION,
        "reason_code": reason_code,
        "upstream_result_kind": str(meta.get("result_kind") or "") or None,
        "upstream_trace_id": str(meta.get("trace_id") or "") or None,
    }


def _pnl_metric_display(value: Any, precision: int) -> str:
    decimal_value = Decimal(str(value)).quantize(
        Decimal("1").scaleb(-precision),
        rounding=ROUND_HALF_UP,
    )
    return f"{decimal_value:,.{precision}f} 元"


def _pnl_metric_card(
    *,
    title: str,
    metric_id: str,
    source_field: str,
    value: Any,
    unit: str,
    precision: int,
) -> dict[str, Any]:
    display = _pnl_metric_display(value, precision)
    decimal_value = Decimal(str(value)).quantize(
        Decimal("1").scaleb(-precision),
        rounding=ROUND_HALF_UP,
    )
    return {
        "type": "metric",
        "title": title,
        "value": display,
        "metric_id": metric_id,
        "spec": {
            "source_field": source_field,
            "raw_value": format(decimal_value, f".{precision}f"),
            "raw_unit": unit,
            "raw_precision": precision,
            "numeric": {
                "raw": float(decimal_value),
                "unit": unit,
                "display": display,
                "precision": precision,
                "sign_aware": True,
            },
        },
    }


def _duration_risk_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    from backend.app.services.risk_tensor_service import risk_tensor_envelope

    repo = RiskTensorRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No risk-tensor report date is available.")
    upstream = risk_tensor_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
    )
    result = dict(upstream.get("result", {}))
    meta = dict(upstream.get("result_meta", {}))
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    requested_currency_basis = _balance_analysis_currency_basis(request)
    cny_risk_contract = requested_currency_basis == "CNY"
    bond_count = int(result.get("bond_count") or 0)
    # Risk Tensor duration unit contract now reports modified duration in years.
    required_numeric_fields = {
        "portfolio_modified_duration": "years",
        "portfolio_dv01": "dv01",
        "portfolio_convexity": "ratio",
        "rate_risk_market_value": "yuan",
        "duration_excluded_market_value": "yuan",
    }
    numeric_contract_complete = all(
        _has_governed_duration_numeric_contract(
            result.get(field_name),
            expected_unit=expected_unit,
        )
        for field_name, expected_unit in required_numeric_fields.items()
    )
    duration_excluded_count = result.get("duration_excluded_count")
    duration_scope_complete = (
        isinstance(duration_excluded_count, int)
        and not isinstance(duration_excluded_count, bool)
    )
    formal_use_allowed = (
        bool(meta.get("formal_use_allowed", False))
        and bond_count > 0
        and cny_risk_contract
        and numeric_contract_complete
        and duration_scope_complete
    )
    upstream_quality = str(meta.get("quality_flag") or result.get("quality_flag") or "warning")
    quality_flag = (
        upstream_quality
        if upstream_quality in {"error", "stale"}
        else "ok"
        if upstream_quality == "ok" and formal_use_allowed
        else "warning"
    )

    cards: list[dict[str, Any]]
    if not cny_risk_contract:
        cards = [
            {
                "type": "status",
                "title": "Currency Basis Requires Review",
                "value": (
                    "Risk Tensor exposes the governed aggregate in CNY; "
                    f"requested currency_basis={requested_currency_basis} was not converted."
                ),
            }
        ]
        answer = (
            f"{report_date} 的 Risk Tensor 仅提供 CNY 正式口径，当前请求为 "
            f"currency_basis={requested_currency_basis}；系统未做币种换算，也未生成正式久期风险指标。"
        )
    elif bond_count <= 0:
        cards = [
            {
                "type": "status",
                "title": "Duration Risk Status",
                "value": "No governed risk-tensor bond rows are available for the selected report date.",
            }
        ]
        answer = (
            f"{report_date} 没有可用的风险张量债券数据；未生成修正久期、DV01 或凸性正式指标。"
        )
    elif not numeric_contract_complete:
        cards = [
            {
                "type": "status",
                "title": "Duration Numeric Contract Incomplete",
                "value": (
                    "One or more governed Risk Tensor Numeric fields are missing raw/display "
                    "values or use an unexpected unit, so formal duration metrics were suppressed."
                ),
            }
        ]
        answer = (
            f"{report_date} 的 Risk Tensor 已返回，但正式 Numeric contract 不完整；"
            "系统已 fail-closed，未生成正式修正久期、DV01、凸性或金额型风险指标。"
        )
    else:
        metric_specs = (
            (
                "Portfolio Modified Duration",
                "MTR-RSK-010",
                "portfolio_modified_duration",
            ),
            ("Portfolio DV01", "MTR-RSK-001", "portfolio_dv01"),
            ("Portfolio Convexity", "MTR-RSK-009", "portfolio_convexity"),
            ("Rate Risk Market Value", "MTR-RSK-021", "rate_risk_market_value"),
            (
                "Duration Excluded Market Value",
                "MTR-RSK-104",
                "duration_excluded_market_value",
            ),
        )
        cards = [
            _duration_numeric_card(
                title=title,
                metric_id=metric_id,
                source_field=source_field,
                value=result.get(source_field),
            )
            for title, metric_id, source_field in metric_specs
            if is_numeric_json(result.get(source_field))
        ]
        if duration_scope_complete:
            assert isinstance(duration_excluded_count, int) and not isinstance(
                duration_excluded_count, bool
            )
            cards.append(
                _duration_count_card(
                    title="Duration Excluded Count",
                    metric_id="MTR-RSK-103",
                    source_field="duration_excluded_count",
                    value=duration_excluded_count,
                )
            )
        cards.append(
            {
                "type": "status",
                "title": "Formal Duration Boundary",
                "value": (
                    "Formal duration uses Risk Tensor modified duration. "
                    "DV01 uses CNY face value × modified duration / 10,000 (CNY/1bp). "
                    "Bond Analytics Macaulay duration is not presented as an approved MTR metric."
                ),
            }
        )
        modified_duration_display = _duration_numeric_display(
            result.get("portfolio_modified_duration")
        )
        dv01_display = _duration_numeric_display(result.get("portfolio_dv01"))
        convexity_display = _duration_numeric_display(result.get("portfolio_convexity"))
        excluded_market_value_display = _duration_numeric_display(
            result.get("duration_excluded_market_value")
        )
        excluded_count_display = (
            f"{duration_excluded_count:,}" if duration_scope_complete else "—"
        )
        answer = (
            f"{report_date} 的正式利率风险摘要已返回：组合修正久期 "
            f"{modified_duration_display}，组合 DV01 {dv01_display} CNY/1bp，"
            f"组合凸性 {convexity_display}。DV01 按 CNY 面值乘修正久期除以 10,000 汇总；"
            f"久期分母排除 {excluded_count_display} 行、"
            f"排除市值 {excluded_market_value_display} 元。"
        )

    return {
        "answer": answer,
        "cards": cards,
        "tables_used": ["fact_formal_risk_tensor_daily"],
        "filters_applied": _audit_filters(
            request,
            report_date,
            resolution=rd_mode,
            extra={
                "currency_basis": requested_currency_basis,
                "governed_currency_basis": "CNY",
            },
        ),
        "row_count": bond_count,
        "sql_executed": _RISK_TENSOR_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_agent_duration_risk",
                "vendor_version": "vv_none",
                "rule_version": RULE_VERSION,
                "cache_version": "cv_agent_duration_risk_v1",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
        ),
        # 久期风险卡固定披露 CNY 口径与张量快照日期，不继承上游日期/金额上下文。
        "amount_currency_basis": "CNY",
        "amount_currency_basis_note": (
            (
                f"Requested currency_basis={requested_currency_basis}; Risk Tensor remained CNY "
                "and formal metric cards were suppressed."
            )
            if not cny_risk_contract
            else "Governed Risk Tensor Numeric contract is incomplete; formal duration metric cards were suppressed."
            if not numeric_contract_complete
            else "DV01 is CNY per 1bp on CNY face value; rate-risk and excluded market values are yuan."
        ),
        "requested_report_date": _requested_report_date(request),
        "resolved_report_date": report_date,
        "as_of_date": report_date,
        "date_basis": "formal_snapshot",
        "fallback_date": None,
        "source_surface": "risk_tensor",
        "result_kind": "agent.duration_risk",
        "next_drill": [
            {"dimension": "tenor_bucket", "label": "按期限桶查看"},
            {"dimension": "duration_exclusions", "label": "查看久期排除项"},
        ],
    }


def _duration_numeric_card(
    *,
    title: str,
    metric_id: str,
    source_field: str,
    value: Any,
) -> dict[str, Any]:
    if not is_numeric_json(value):
        raise ValueError(f"Governed Numeric is required for duration field {source_field}.")
    numeric = dict(value)
    raw = numeric.get("raw")
    precision = int(numeric.get("precision") or 0)
    display = str(numeric.get("display") or "—")
    return {
        "type": "metric",
        "title": title,
        "value": display,
        "spec": {
            "metric_id": metric_id,
            "source_field": source_field,
            "raw_value": None if raw is None else str(raw),
            "raw_unit": str(numeric.get("unit") or ""),
            "raw_precision": precision,
            "numeric": numeric,
        },
    }


def _duration_count_card(
    *,
    title: str,
    metric_id: str,
    source_field: str,
    value: int,
) -> dict[str, Any]:
    numeric = {
        "raw": value,
        "unit": "count",
        "display": f"{value:,}",
        "precision": 0,
        "sign_aware": False,
    }
    return _duration_numeric_card(
        title=title,
        metric_id=metric_id,
        source_field=source_field,
        value=numeric,
    )


def _has_governed_duration_numeric_contract(
    value: Any,
    *,
    expected_unit: str,
) -> bool:
    if not is_numeric_json(value):
        return False
    raw = value.get("raw")
    display = str(value.get("display") or "").strip()
    unit = str(value.get("unit") or "").strip()
    return raw is not None and bool(display) and unit == expected_unit


def _duration_numeric_display(value: Any) -> str:
    if not is_numeric_json(value):
        return "—"
    return str(value.get("display") or "—")


def _credit_exposure_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    from backend.app.services.bond_analytics_service import (
        bond_analytics_credit_exposure_governance_meta,
    )

    repo = BondAnalyticsRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No bond-analytics report date is available.")
    summary = repo.fetch_credit_summary(report_date=report_date)
    governance_meta = bond_analytics_credit_exposure_governance_meta(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
    )
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    credit_bond_count = int(summary.get("credit_bond_count") or 0)
    # fail-closed：无信用债敞口行或汇总字段缺失（SQL 空集聚合返回 NULL）时，
    # 不得宣称正式口径。
    summary_values_complete = all(
        summary.get(field) is not None
        for field in ("credit_market_value", "spread_dv01", "oci_credit_exposure")
    )
    formal_use_allowed = (
        bool(governance_meta.get("formal_use_allowed", False))
        and credit_bond_count > 0
        and summary_values_complete
    )
    quality_flag: Literal["ok", "warning"] = "ok" if formal_use_allowed else "warning"
    if credit_bond_count <= 0:
        answer = (
            f"{report_date} 没有受治理的信用债敞口记录；"
            "未生成正式信用暴露指标，本结果按非正式口径返回（formal_use_allowed=false）。"
        )
    elif not summary_values_complete:
        answer = (
            f"{report_date} 的信用暴露汇总字段不完整；"
            "系统已 fail-closed，本结果按非正式口径返回（formal_use_allowed=false）。"
        )
    else:
        answer = (
            f"{report_date} 的信用暴露摘要已返回，信用债 {credit_bond_count} 只，"
            f"信用市值 {summary['credit_market_value']}。"
        )
    if credit_bond_count > 0 and summary_values_complete and not governance_meta.get("formal_use_allowed"):
        reason = str(governance_meta.get("fallback_reason") or "bond analytics governance lineage unavailable")
        answer += (
            "Bond Analytics 正式治理 run 或 lineage 不完整；"
            f"系统已 fail-closed，本结果按非正式口径返回（formal_use_allowed=false）。原因：{reason}"
        )
    return {
        "answer": answer,
        "cards": [
            {"type": "metric", "title": "Credit Bond Count", "value": str(summary["credit_bond_count"])},
            {"type": "metric", "title": "Credit Market Value", "value": str(summary["credit_market_value"])},
            {"type": "metric", "title": "Spread DV01", "value": str(summary["spread_dv01"])},
            {"type": "metric", "title": "OCI Credit Exposure", "value": str(summary["oci_credit_exposure"])},
        ],
        "tables_used": ["fact_formal_bond_analytics_daily"],
        "filters_applied": _audit_filters(request, report_date, resolution=rd_mode),
        "row_count": credit_bond_count,
        "sql_executed": _CREDIT_EXPOSURE_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            governance_meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_bond_analytics_empty",
                "vendor_version": "vv_none",
                "rule_version": RULE_VERSION,
                "cache_version": "cv_agent_credit_exposure_v1",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            inherit_context=True,
            context_defaults={
                "requested_report_date": _requested_report_date(request),
                "resolved_report_date": report_date,
                "as_of_date": report_date,
                "date_basis": "bond_analytics_report_date",
                "source_surface": "bond_analytics",
            },
        ),
        "fallback_reason": governance_meta.get("fallback_reason"),
        "result_kind": "agent.credit_exposure",
        "next_drill": [
            {"dimension": "issuer", "label": "按发行人查看"},
            {"dimension": "rating", "label": "按评级查看"},
        ],
    }


def _product_pnl_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    from backend.app.services.product_category_pnl_service import product_category_pnl_envelope

    repo = ProductCategoryPnlRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No product-category report date is available.")
    view = str(request.filters.get("view") or "monthly")
    upstream = product_category_pnl_envelope(
        duckdb_path,
        report_date=report_date,
        view=view,
    )
    result = dict(cast(Mapping[str, Any], upstream.get("result") or {}))
    meta = dict(cast(Mapping[str, Any], upstream.get("result_meta") or {}))
    rows = list(result.get("rows") or [])
    if not rows:
        raise ValueError(f"No product-category rows for report_date={report_date} view={view}.")
    # fail-closed：grand_total 行缺失时不得静默用首行冒充总计。
    upstream_grand_total = result.get("grand_total")
    grand_total_row: dict[str, Any] | None = next(
        (row for row in rows if str(row.get("category_id")) == "grand_total"),
        upstream_grand_total if isinstance(upstream_grand_total, dict) and upstream_grand_total else None,
    )
    grand_total: dict[str, Any] = dict(grand_total_row or {})
    asset_total = dict(result.get("asset_total") or {})
    if not asset_total:
        asset_total = next(
            (row for row in rows if str(row.get("category_id")) == "asset_total"),
            {},
        )
    liability_total = dict(result.get("liability_total") or {})
    if not liability_total:
        liability_total = next(
            (row for row in rows if str(row.get("category_id")) == "liability_total"),
            {},
        )
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    formal_use_allowed = grand_total_row is not None
    upstream_quality = str(meta.get("quality_flag") or "warning")
    quality_flag: Literal["ok", "warning"] = (
        "ok" if upstream_quality == "ok" and formal_use_allowed else "warning"
    )
    answer = f"{report_date} 的产品损益视图已返回，当前 view={view}。"
    if grand_total_row is None:
        answer += (
            "读模型缺少 grand_total 汇总行；"
            "系统已 fail-closed，未生成正式总计指标（formal_use_allowed=false）。"
        )
    return {
        "answer": answer,
        "cards": [
            {"type": "metric", "title": "Grand Total", "value": str(grand_total.get("business_net_income", ""))},
            {"type": "metric", "title": "Asset Total", "value": str(asset_total.get("business_net_income", ""))},
            {
                "type": "metric",
                "title": "Liability Total",
                "value": str(liability_total.get("business_net_income", "")),
            },
            {"type": "table", "title": "Product Rows", "data": rows[:10]},
        ],
        "tables_used": ["product_category_pnl_formal_read_model"],
        "filters_applied": _audit_filters(
            request,
            report_date,
            resolution=rd_mode,
            extra={"view": view},
        ),
        "row_count": len(rows),
        "sql_executed": _PRODUCT_PNL_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_product_pnl_lineage_unavailable",
                "vendor_version": "vv_none",
                "rule_version": RULE_VERSION,
                "cache_version": "cv_agent_product_pnl_v1",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            inherit_context=True,
            context_defaults={
                "requested_report_date": _requested_report_date(request),
                "resolved_report_date": report_date,
                "as_of_date": report_date,
            },
        ),
        "result_kind": "agent.product_pnl",
        "next_drill": [{"dimension": "product_category", "label": "按产品分类查看"}],
    }


def _pnl_bridge_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    # sql_executed：披露桥接输入事实的主干只读拉取；曲线/FX/内存归因不在此展开。
    from backend.app.services.pnl_bridge_service import pnl_bridge_envelope

    repo = PnlRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_formal_fi_report_dates())
    if report_date is None:
        raise ValueError("No PnL bridge report date is available.")
    upstream = pnl_bridge_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
    )
    summary = dict(upstream.get("result", {}).get("summary", {}))
    meta = dict(upstream.get("result_meta", {}))
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    base_filters = _audit_filters(request, report_date, resolution=rd_mode)
    quality_flag = str(meta.get("quality_flag") or "warning")
    # fail-closed：上游 result_meta 缺 formal_use_allowed 口径标记时默认拒绝而非放行。
    formal_marker_missing = "formal_use_allowed" not in meta
    formal_use_allowed = bool(meta.get("formal_use_allowed", False)) and quality_flag != "error"
    if formal_marker_missing and quality_flag == "ok":
        quality_flag = "warning"
    answer = f"{report_date} 的 PnL bridge 已返回。"
    # Human: caliber-formal_scenario_gate-justified -- fail-closed disclosure
    # branch: when upstream result_meta lacks the formal_use_allowed marker we
    # refuse formal use (formal_use_allowed=False) and say so in the answer;
    # this cannot authorize formal or scenario use.
    if formal_marker_missing:
        answer += (
            "上游 result_meta 缺少 formal_use_allowed 口径标记；"
            "系统已 fail-closed，本结果按非正式口径返回（formal_use_allowed=false）。"
        )
    return {
        "answer": answer,
        "cards": [
            _agent_metric_card("Explained PnL", summary.get("total_explained_pnl")),
            _agent_metric_card("Actual PnL", summary.get("total_actual_pnl")),
            _agent_metric_card("Residual", summary.get("total_residual")),
        ],
        "tables_used": ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
        "filters_applied": base_filters,
        "row_count": int(summary.get("row_count", 0)),
        "sql_executed": _PNL_BRIDGE_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_agent_pnl_bridge",
                "vendor_version": "vv_none",
                "rule_version": RULE_VERSION,
                "cache_version": "cv_agent_pnl_bridge_v1",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
        ),
        "result_kind": "agent.pnl_bridge",
        "next_drill": [{"dimension": "instrument", "label": "按券桥接查看"}],
    }


def _agent_metric_card(title: str, value: Any) -> dict[str, Any]:
    if is_numeric_json(value):
        display = str(value.get("display") or "--")
        unit = str(value.get("unit") or "").strip()
        return {
            "type": "metric",
            "title": title,
            "value": f"{display} {unit}".strip(),
            "spec": {"numeric": dict(value)},
        }
    return {
        "type": "metric",
        "title": title,
        "value": "" if value is None else str(value),
    }


def _risk_tensor_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    from backend.app.services.risk_tensor_service import risk_tensor_envelope

    # latest 日期必须来自张量事实表本身（与 _duration_risk_payload 对齐）：
    # bond analytics 领先张量落表时，用 BondAnalyticsRepository 的最新日期会让
    # risk_tensor_envelope 直接 raise。
    repo = RiskTensorRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No risk-tensor report date is available.")
    upstream = risk_tensor_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date,
    )
    result = dict(upstream.get("result", {}))
    meta = dict(upstream.get("result_meta", {}))
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    quality_flag = str(meta.get("quality_flag") or "warning")
    # fail-closed：上游 result_meta 缺 formal_use_allowed 口径标记时默认拒绝而非放行。
    formal_marker_missing = "formal_use_allowed" not in meta
    formal_use_allowed = bool(meta.get("formal_use_allowed", False))
    if formal_marker_missing and quality_flag == "ok":
        quality_flag = "warning"
    answer = f"{report_date} 的风险张量已返回。"
    # Human: caliber-formal_scenario_gate-justified -- fail-closed disclosure
    # branch: when upstream result_meta lacks the formal_use_allowed marker we
    # refuse formal use (formal_use_allowed=False) and say so in the answer;
    # this cannot authorize formal or scenario use.
    if formal_marker_missing:
        answer += (
            "上游 result_meta 缺少 formal_use_allowed 口径标记；"
            "系统已 fail-closed，本结果按非正式口径返回（formal_use_allowed=false）。"
        )
    return {
        "answer": answer,
        "cards": [
            # 上游经 promote_flat_payload 产出 Numeric dict；复用 pnl_bridge 同款
            # 渲染取 display 字段，避免把 {'raw': ...} 字典串直接落在指标卡上。
            _agent_metric_card("Portfolio DV01", result.get("portfolio_dv01")),
            _agent_metric_card("CS01", result.get("cs01")),
            _agent_metric_card("Portfolio Convexity", result.get("portfolio_convexity")),
        ],
        "tables_used": ["fact_formal_risk_tensor_daily"],
        "filters_applied": _audit_filters(request, report_date, resolution=rd_mode),
        "row_count": int(result.get("bond_count", 0)),
        "sql_executed": _RISK_TENSOR_SQL_DISCLOSURE,
        "quality_flag": quality_flag,
        **_upstream_meta_projection(
            meta,
            agent_formal_gate=formal_use_allowed,
            governance_defaults={
                "basis": "formal",
                "source_version": "sv_agent_risk_tensor",
                "vendor_version": "vv_none",
                "rule_version": RULE_VERSION,
                "cache_version": "cv_agent_risk_tensor_v1",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
        ),
        "result_kind": "agent.risk_tensor",
        "next_drill": [{"dimension": "krd_bucket", "label": "按KRD桶查看"}],
    }


def _market_data_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    # sql_executed：披露 macro 最近点与 formal FX mid 主干只读模板；tushare 补充链路不在此展开。
    from backend.app.services.macro_vendor_service import (
        choice_macro_latest_envelope,
        fx_analytical_envelope,
        fx_formal_status_envelope,
    )

    macro_upstream = choice_macro_latest_envelope(duckdb_path)
    fx_upstream = fx_analytical_envelope(duckdb_path)
    meta = dict(macro_upstream.get("result_meta", {}))
    series = list(macro_upstream.get("result", {}).get("series", []))
    fx_groups = list(fx_upstream.get("result", {}).get("groups", []))
    fx_rows: list[dict[str, Any]] = []
    fx_formal_meta: dict[str, Any] = {}
    formal_fx_warning: str | None = None
    try:
        fx_formal_upstream = fx_formal_status_envelope(duckdb_path)
        fx_formal_meta = dict(fx_formal_upstream.get("result_meta", {}))
        fx_rows = list(fx_formal_upstream.get("result", {}).get("rows", []))
    except FileNotFoundError:
        formal_fx_warning = "Formal FX catalog unavailable; market-data response degraded to macro-only view."
    if formal_fx_warning is None and (
        str(fx_formal_meta.get("vendor_status") or "") == "vendor_unavailable" or not fx_rows
    ):
        formal_fx_warning = "Formal FX candidates unavailable; market-data response degraded to macro-only view."

    cards: list[dict[str, Any]] = [
        {"type": "metric", "title": "Series Count", "value": str(len(series))},
        {"type": "metric", "title": "Formal FX Candidates", "value": str(len(fx_rows))},
        {"type": "metric", "title": "Analytical FX Groups", "value": str(len(fx_groups))},
        {"type": "table", "title": "Latest Macro Series", "data": series[:10]},
        {"type": "table", "title": "Formal FX Status", "data": fx_rows[:10]},
    ]
    if formal_fx_warning is not None:
        cards.append({"type": "status", "title": "Formal FX Status Warning", "value": formal_fx_warning})
    return {
        "answer": (
            "Latest governed market-data payload returned, including macro series plus analytical FX surfaces."
            if formal_fx_warning is None
            else "Latest governed market-data payload returned with degraded formal FX coverage."
        ),
        "cards": cards,
        "tables_used": ["fact_choice_macro_daily", "fx_daily_mid"],
        "filters_applied": _audit_filters(request, None, resolution="not_applicable"),
        "row_count": len(series) + len(fx_rows),
        "sql_executed": _MARKET_DATA_SQL_DISCLOSURE,
        "quality_flag": "warning" if formal_fx_warning is not None else str(meta.get("quality_flag") or "warning"),
        "basis": "analytical",
        "formal_use_allowed": False,
        "scenario_flag": False,
        "source_version": str(meta.get("source_version") or "sv_agent_market_data"),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta.get("rule_version") or RULE_VERSION),
        "cache_version": str(meta.get("cache_version") or "cv_agent_market_data_v1"),
        "vendor_status": "vendor_unavailable" if formal_fx_warning is not None else str(meta.get("vendor_status") or "ok"),
        "fallback_mode": str(meta.get("fallback_mode") or "none"),
        "result_kind": "agent.market_data",
        "next_drill": [{"dimension": "series_id", "label": "Inspect macro or FX series"}],
    }


def _news_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    # sql_executed：静态模板部分固化在 _NEWS_SQL_DISCLOSURE，运行期仅按本次相同
    # 过滤条件填充 where 子句（choice_news_filters 与执行链路同源），仅披露不执行。
    from backend.app.services.choice_news_service import choice_news_latest_envelope

    limit = int(request.filters.get("limit") or 20)
    upstream = choice_news_latest_envelope(
        duckdb_path,
        limit=limit,
        offset=int(request.filters.get("offset") or 0),
        group_id=request.filters.get("group_id"),
        topic_code=request.filters.get("topic_code"),
        error_only=bool(request.filters.get("error_only", False)),
        received_from=request.filters.get("received_from"),
        received_to=request.filters.get("received_to"),
    )
    # 与 choice_news_latest_sql_disclosure 的既有默认一致：received_to 缺省回落当日，
    # 过滤值全部保持 `?` 绑定占位，不进入披露文本。
    where_clause, _params = choice_news_filters(
        group_id=request.filters.get("group_id"),
        topic_code=request.filters.get("topic_code"),
        stock_filter_tokens=[],
        stock_match_mode="best_effort",
        error_only=bool(request.filters.get("error_only", False)),
        received_from=request.filters.get("received_from"),
        received_to=request.filters.get("received_to") or date.today().isoformat(),
    )
    sql_disclosure = [
        statement.format(where_clause=where_clause)
        for statement in _NEWS_SQL_DISCLOSURE
    ]
    meta = dict(upstream.get("result_meta", {}))
    result = dict(upstream.get("result", {}))
    events = list(result.get("events", []))
    return {
        "answer": "最新新闻事件已返回。",
        "cards": [
            {"type": "metric", "title": "Event Count", "value": str(result.get("total_rows", 0))},
            {"type": "table", "title": "Latest Events", "data": events[:10]},
        ],
        "tables_used": ["choice_news_event"],
        "filters_applied": _audit_filters(request, None, resolution="not_applicable"),
        "row_count": len(events),
        "sql_executed": sql_disclosure,
        "quality_flag": str(meta.get("quality_flag") or "ok"),
        "basis": str(meta.get("basis") or "analytical"),
        "formal_use_allowed": bool(meta.get("formal_use_allowed", False)),
        "scenario_flag": bool(meta.get("scenario_flag", False)),
        "source_version": str(meta.get("source_version") or "sv_agent_news"),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta.get("rule_version") or RULE_VERSION),
        "cache_version": str(meta.get("cache_version") or "cv_agent_news_v1"),
        "vendor_status": str(meta.get("vendor_status") or "ok"),
        "fallback_mode": str(meta.get("fallback_mode") or "none"),
        "result_kind": "agent.news",
        "next_drill": [{"dimension": "topic_code", "label": "按主题查看"}],
    }


def _pretrade_checklist_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    """盘前操作清单意图：只读转发 pretrade_checklist_service，观察面输出。

    sql_executed 披露主干只读模板（_PRETRADE_CHECKLIST_SQL_DISCLOSURE）；
    门控敞口轻读不在披露中展开。服务返回 None（库/候选历史表缺失、无信号日）
    时降级为「数据未生成」文案，不抛错、不编造清单。
    """
    from backend.app.governance.settings import get_settings
    from backend.app.repositories.duckdb_read_context import DuckDBReadSelectionError
    from backend.app.repositories.financial_result_publication_repo import FinancialPublicationError
    from backend.app.repositories.system_read_publication_repo import (
        current_system_read_context,
        system_read_scope,
    )
    from backend.app.services.pretrade_checklist_service import pretrade_checklist_envelope

    raw_as_of = str(request.filters.get("as_of_date") or "").strip()
    requested_as_of = raw_as_of or _requested_report_date(request)
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if requested_as_of else "latest_default"
    )
    page_filters = (
        request.page_context.current_filters
        if request.page_context is not None
        else {}
    )
    selected_generation = str(page_filters.get("system_read_generation") or "").strip()
    unavailable_reason: str | None = None
    upstream: dict[str, object] | None = None
    if not selected_generation:
        unavailable_reason = "system_read_generation_missing"
    else:
        try:
            with system_read_scope(get_settings(), generation=selected_generation):
                selected_context = current_system_read_context()
                if (
                    selected_context is None
                    or selected_context.generation != selected_generation
                ):
                    unavailable_reason = "system_read_generation_unavailable"
                else:
                    upstream = pretrade_checklist_envelope(
                        duckdb_path=duckdb_path,
                        as_of_date=requested_as_of,
                    )
        except (DuckDBReadSelectionError, FinancialPublicationError):
            unavailable_reason = "system_read_generation_unavailable"
    if upstream is None:
        detail = unavailable_reason or (
            "livermore_candidate_history 无 factor_screen 信号日或数据面不可用。"
        )
        return {
            "answer": (
                f"盘前操作清单不可用：{detail}"
                "本轮未产出可买、复核或仓位提示。"
            ),
            "cards": [
                {
                    "type": "status",
                    "title": "Pretrade Checklist Unavailable",
                    "value": detail,
                }
            ],
            "tables_used": ["livermore_candidate_history"],
            "filters_applied": _audit_filters(
                request,
                requested_as_of,
                resolution=rd_mode,
                extra={
                    "signal_kind": "factor_screen",
                    "system_read_generation": selected_generation or None,
                    "pretrade_unavailable_reason": unavailable_reason,
                },
            ),
            "row_count": 0,
            "sql_executed": _PRETRADE_CHECKLIST_SQL_DISCLOSURE,
            "quality_flag": "warning",
            "basis": "analytical",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "source_version": "sv_pretrade_checklist_unavailable",
            "rule_version": "rv_pretrade_checklist_v1",
            "cache_version": "cv_agent_pretrade_checklist_v1",
            "result_kind": "agent.pretrade_checklist",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "next_drill": [],
        }

    result = dict(upstream.get("result", {}))
    meta = dict(upstream.get("result_meta", {}))
    items = [item for item in result.get("items", []) if isinstance(item, dict)]
    summary = dict(result.get("summary", {}))
    staleness = dict(result.get("staleness", {}))
    gate = dict(result.get("gate", {}))
    as_of = str(result.get("as_of_date") or "")
    checklist_status = str(result.get("checklist_status") or "empty")
    qualification = dict(
        result.get("qualification")
        or result.get("pretrade_qualification")
        or {}
    )
    if checklist_status == "unavailable" or qualification.get("status") == "unavailable":
        qualification_reason = str(
            qualification.get("reason")
            or "completed_pretrade_provenance_missing"
        )
        return {
            "answer": (
                f"盘前操作清单不可用：{qualification_reason}。"
                "本轮未产出可买、复核或仓位提示。"
            ),
            "cards": [
                {
                    "type": "status",
                    "title": "Pretrade Checklist Unavailable",
                    "value": qualification_reason,
                }
            ],
            "tables_used": list(meta.get("tables_used") or ["livermore_candidate_history"]),
            "filters_applied": _audit_filters(
                request,
                as_of or requested_as_of,
                resolution=rd_mode,
                extra={
                    "signal_kind": result.get("signal_kind"),
                    "checklist_status": "unavailable",
                    "system_read_generation": selected_generation,
                    "pretrade_unavailable_reason": qualification_reason,
                },
            ),
            "row_count": 0,
            "sql_executed": _PRETRADE_CHECKLIST_SQL_DISCLOSURE,
            "quality_flag": "warning",
            "basis": "analytical",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "source_version": str(meta.get("source_version") or "sv_pretrade_checklist_unavailable"),
            "vendor_version": str(meta.get("vendor_version") or "vv_none"),
            "rule_version": str(meta.get("rule_version") or "rv_pretrade_checklist_v1"),
            "cache_version": str(meta.get("cache_version") or "cv_agent_pretrade_checklist_v1"),
            "result_kind": "agent.pretrade_checklist",
            "vendor_status": str(meta.get("vendor_status") or "ok"),
            "fallback_mode": str(meta.get("fallback_mode") or "none"),
            "requested_report_date": requested_as_of,
            "resolved_report_date": as_of or None,
            "as_of_date": str(meta.get("as_of_date") or as_of or "") or None,
            "date_basis": "livermore_signal_snapshot_as_of_date",
            "next_drill": [],
        }

    buyable_items = [item for item in items if str(item.get("buyable_status")) == "buyable"]
    blocked_items = [
        item
        for item in items
        if str(item.get("buyable_status")) in {"blocked_suspended", "blocked_limit"}
    ]
    attention_items = [
        item
        for item in items
        if str(item.get("buyable_status")) in {"review", "data_missing"}
    ]
    buyable_count = int(summary.get("buyable_count", len(buyable_items)))
    blocked_count = int(summary.get("blocked_count", len(blocked_items)))

    answer_parts = [
        f"{as_of} 盘前操作清单已返回：候选 {len(items)} 只，可买 {buyable_count} 只，"
        f"拦截 {blocked_count} 只，复核/数据缺失 {len(attention_items)} 只。"
    ]
    if checklist_status == "stale":
        answer_parts.append(
            f"注意：信号日距今天 {staleness.get('calendar_gap_days')} 个自然日，"
            f"已超过 stale 阈值 {staleness.get('stale_calendar_days')} 天，"
            "候选可能过期，执行前请先刷新信号。"
        )
    elif checklist_status == "empty":
        answer_parts.append("该信号日没有候选行（无候选），本轮无可买判定。")
    if buyable_items:
        buyable_text = "、".join(_pretrade_item_label(item) for item in buyable_items[:10])
        suffix = " 等" if len(buyable_items) > 10 else ""
        answer_parts.append(f"可买：{buyable_text}{suffix}。")
    if blocked_items:
        blocked_text = "；".join(
            f"{_pretrade_item_label(item)}（{_pretrade_reasons_text(item)}）"
            for item in blocked_items[:10]
        )
        answer_parts.append(f"拦截：{blocked_text}。")
    if gate.get("status") != "available":
        answer_parts.append(str(gate.get("note") or "门控敞口不可用，字段缺省，不代表门控放行。"))
    answer_parts.append(str(result.get("disclaimer") or ""))

    cards: list[dict[str, Any]] = [
        {"type": "metric", "title": "Signal Date", "value": as_of},
        {"type": "metric", "title": "Checklist Status", "value": checklist_status},
        {"type": "metric", "title": "Buyable Count", "value": str(buyable_count)},
        {"type": "metric", "title": "Blocked Count", "value": str(blocked_count)},
    ]
    if checklist_status == "stale":
        cards.append(
            {
                "type": "status",
                "title": "Stale Signal Warning",
                "value": (
                    f"信号日 {as_of} 距 {staleness.get('today')} 已 "
                    f"{staleness.get('calendar_gap_days')} 个自然日"
                    f"（阈值 {staleness.get('stale_calendar_days')} 天），候选可能过期。"
                ),
            }
        )
    if gate.get("status") == "available":
        cards.append(
            {
                "type": "metric",
                "title": "Gate Exposure",
                "value": f"{gate.get('state')} / {gate.get('exposure')}",
            }
        )
    else:
        cards.append(
            {
                "type": "status",
                "title": "Gate Exposure Degraded",
                "value": str(gate.get("note") or "门控敞口不可用，字段缺省。"),
            }
        )
    if buyable_items:
        cards.append(
            {
                "type": "table",
                "title": "Buyable Candidates",
                "data": [_pretrade_item_row(item) for item in buyable_items[:10]],
            }
        )
    if blocked_items or attention_items:
        cards.append(
            {
                "type": "table",
                "title": "Blocked / Review Candidates",
                "data": [
                    _pretrade_item_row(item)
                    for item in (blocked_items + attention_items)[:10]
                ],
            }
        )
    cards.append(
        {
            "type": "status",
            "title": "Disclaimer",
            "value": str(result.get("disclaimer") or "观察面输出：盘前检查仅供复核参考，不构成交易指令。"),
        }
    )

    return {
        "answer": "".join(part for part in answer_parts if part),
        "cards": cards,
        "tables_used": list(
            meta.get("tables_used")
            or [
                "livermore_candidate_history",
                "choice_stock_daily_observation",
                "stock_limit_price_daily",
                "stock_adjustment_factor",
            ]
        ),
        "filters_applied": _audit_filters(
            request,
            as_of or None,
            resolution=rd_mode,
            extra={
                "signal_kind": result.get("signal_kind"),
                "top_n": result.get("top_n"),
                "checklist_status": checklist_status,
                "system_read_generation": selected_generation,
            },
        ),
        "row_count": len(items),
        "sql_executed": _PRETRADE_CHECKLIST_SQL_DISCLOSURE,
        "quality_flag": str(meta.get("quality_flag") or "warning"),
        "basis": str(meta.get("basis") or "analytical"),
        "formal_use_allowed": bool(meta.get("formal_use_allowed", False)),
        "scenario_flag": False,
        "source_version": str(meta.get("source_version") or "sv_pretrade_checklist_unavailable"),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta.get("rule_version") or "rv_pretrade_checklist_v1"),
        "cache_version": str(meta.get("cache_version") or "cv_agent_pretrade_checklist_v1"),
        "result_kind": "agent.pretrade_checklist",
        "vendor_status": str(meta.get("vendor_status") or "ok"),
        "fallback_mode": str(meta.get("fallback_mode") or "none"),
        "requested_report_date": requested_as_of,
        "resolved_report_date": as_of or None,
        "as_of_date": str(meta.get("as_of_date") or as_of or "") or None,
        "date_basis": "livermore_signal_snapshot_as_of_date",
        "next_drill": [],
    }


def _pretrade_item_label(item: dict[str, Any]) -> str:
    code = str(item.get("stock_code") or "").strip()
    name = str(item.get("stock_name") or "").strip()
    return f"{code} {name}".strip() or "未知候选"


def _pretrade_reasons_text(item: dict[str, Any]) -> str:
    reasons = item.get("block_reasons")
    if not isinstance(reasons, list) or not reasons:
        return "无拦截原因"
    return "、".join(
        _PRETRADE_BLOCK_REASON_LABELS.get(str(reason), str(reason)) for reason in reasons
    )


def _pretrade_item_row(item: dict[str, Any]) -> dict[str, Any]:
    limit_check = item.get("limit_check") if isinstance(item.get("limit_check"), dict) else {}
    position_hint = (
        item.get("position_hint") if isinstance(item.get("position_hint"), dict) else None
    )
    status = str(item.get("buyable_status") or "")
    return {
        "candidate_rank": item.get("candidate_rank"),
        "stock_code": item.get("stock_code"),
        "stock_name": item.get("stock_name"),
        "sector_name": item.get("sector_name"),
        "buyable_status": status,
        "status_label": _PRETRADE_STATUS_LABELS.get(status, status),
        "block_reasons": _pretrade_reasons_text(item) if item.get("block_reasons") else "",
        "close_value": item.get("close_value"),
        "amount_rmb": item.get("amount_rmb"),
        "limit_status": limit_check.get("status"),
        "position_hint": position_hint,
    }


def _walk_forward_verdict_payload(request: AgentQueryRequest) -> dict[str, Any]:
    """策略样本外验证判定意图：只读转发 strategy_report_service 的展示裁剪。

    数据源是落盘 walk-forward JSON 报告（非 DuckDB 查询），sql_executed 保持 []；
    报告路径作为证据引用写入 tables_used 与 filters_applied。报告缺失/不可解析
    时降级为「报告未生成」文案，不抛错、不重算指标。
    """
    from backend.app.services.strategy_report_service import (
        resolve_walk_forward_report_path,
        walk_forward_summary_envelope,
    )

    report_ref = _walk_forward_report_reference(resolve_walk_forward_report_path())
    upstream = walk_forward_summary_envelope()
    if upstream is None:
        return {
            "answer": (
                f"策略样本外验证报告未生成：{report_ref} 缺失或不可解析，"
                "本轮没有可引用的 walk-forward 判定，也未重算任何指标。"
            ),
            "cards": [
                {
                    "type": "status",
                    "title": "Walk-Forward Report Unavailable",
                    "value": "落盘报告缺失或不可解析，请先运行 walk-forward 验证脚本生成报告。",
                },
                {"type": "resource", "title": "Walk-Forward Report", "value": report_ref},
            ],
            "tables_used": [report_ref],
            "filters_applied": _audit_filters(
                request,
                None,
                resolution="not_applicable",
                extra={"report_path": report_ref},
            ),
            "row_count": 0,
            "sql_executed": [],
            "quality_flag": "warning",
            "basis": "analytical",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "source_version": "sv_walk_forward_report_unavailable",
            "rule_version": "rv_walk_forward_display_trim_v1",
            "cache_version": "cv_agent_walk_forward_verdict_v1",
            "result_kind": "agent.walk_forward_verdict",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "next_drill": [],
        }

    summary = dict(upstream.get("result", {}))
    meta = dict(upstream.get("result_meta", {}))
    rows: list[dict[str, Any]] = []
    schedules = summary.get("schedules")
    for schedule in schedules if isinstance(schedules, list) else []:
        if not isinstance(schedule, dict):
            continue
        label = schedule.get("label")
        strategies = schedule.get("strategies")
        for strategy in strategies if isinstance(strategies, list) else []:
            if not isinstance(strategy, dict):
                continue
            sign = strategy.get("excess_sign_consistency")
            sign = sign if isinstance(sign, dict) else {}
            risk_budget = strategy.get("risk_budget")
            risk_budget = risk_budget if isinstance(risk_budget, dict) else {}
            rows.append(
                {
                    "schedule": label,
                    "strategy": strategy.get("strategy"),
                    "verdict": strategy.get("verdict"),
                    "verdict_label": _walk_forward_verdict_label(strategy.get("verdict")),
                    "verdict_reason": strategy.get("verdict_reason"),
                    "oos_window_count": strategy.get("oos_window_count"),
                    "in_sample_excess": strategy.get("in_sample_excess"),
                    "oos_excess_median": strategy.get("oos_excess_median"),
                    "oos_chain_excess": strategy.get("oos_chain_excess"),
                    "positive_ratio": sign.get("positive_ratio"),
                    "decay_status": strategy.get("decay_cumulative_status"),
                    "rpt_switch_rate": risk_budget.get("switch_rate"),
                }
            )

    verdict_counts = {"oos_supported": 0, "oos_weakened": 0, "insufficient_windows": 0}
    for row in rows:
        verdict = str(row.get("verdict") or "")
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1
    answer_parts = [
        f"策略样本外验证判定已返回：共 {len(rows)} 条策略×周期判定"
        f"（样本外支持 {verdict_counts['oos_supported']}、"
        f"样本外衰减 {verdict_counts['oos_weakened']}、"
        f"样本不足 {verdict_counts['insufficient_windows']}）。"
    ]
    if not rows:
        answer_parts.append("报告已读取，但未包含任何策略判定（无候选策略）。")
    else:
        lines = [
            (
                f"{row.get('strategy')}[{row.get('schedule')}]：{row.get('verdict_label')}"
                f"（样本内超额 {_walk_forward_number(row.get('in_sample_excess'))}，"
                f"样本外链式超额 {_walk_forward_number(row.get('oos_chain_excess'))}，"
                f"正超额窗口占比 {_walk_forward_number(row.get('positive_ratio'))}，"
                f"窗口数 {_walk_forward_number(row.get('oos_window_count'))}）"
            )
            for row in rows[:8]
        ]
        answer_parts.append("；".join(lines) + "。")
        if len(rows) > 8:
            answer_parts.append(f"其余 {len(rows) - 8} 条见判定明细表。")
    answer_parts.append("判定与数字均来自落盘 walk-forward 报告，未重算任何指标。")

    quality_flag = "warning" if not rows else str(meta.get("quality_flag") or "warning")
    cards: list[dict[str, Any]] = [
        {"type": "metric", "title": "Strategy Verdicts", "value": str(len(rows))},
        {"type": "metric", "title": "Generated At", "value": str(summary.get("generated_at") or "unknown")},
        {"type": "metric", "title": "Engine Version", "value": str(summary.get("engine_version") or "unknown")},
        {"type": "metric", "title": "Report Issues", "value": str(summary.get("issue_count", 0))},
    ]
    if rows:
        cards.append(
            {
                "type": "table",
                "title": "Walk-Forward Strategy Verdicts",
                "data": rows[:50],
            }
        )
    cards.append({"type": "resource", "title": "Walk-Forward Report", "value": report_ref})

    return {
        "answer": "".join(answer_parts),
        "cards": cards,
        "tables_used": [report_ref],
        "filters_applied": _audit_filters(
            request,
            None,
            resolution="not_applicable",
            extra={
                "report_path": report_ref,
                "generated_at": summary.get("generated_at"),
            },
        ),
        "row_count": len(rows),
        "sql_executed": [],
        "quality_flag": quality_flag,
        "basis": str(meta.get("basis") or "analytical"),
        "formal_use_allowed": bool(meta.get("formal_use_allowed", False)),
        "scenario_flag": False,
        "source_version": str(meta.get("source_version") or "sv_walk_forward_report_unknown"),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta.get("rule_version") or "rv_walk_forward_display_trim_v1"),
        "cache_version": str(meta.get("cache_version") or "cv_agent_walk_forward_verdict_v1"),
        "result_kind": "agent.walk_forward_verdict",
        "vendor_status": str(meta.get("vendor_status") or "ok"),
        "fallback_mode": str(meta.get("fallback_mode") or "none"),
        "next_drill": [],
    }


def _walk_forward_verdict_label(verdict: Any) -> str:
    text = str(verdict or "").strip()
    return _WALK_FORWARD_VERDICT_LABELS.get(text, text or "未知判定")


def _walk_forward_number(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def _walk_forward_report_reference(report_path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        return report_path.resolve().relative_to(repo_root).as_posix()
    except (OSError, ValueError):
        return str(report_path)


def _semantic_query_audit_fields(request: AgentQueryRequest) -> dict[str, Any]:
    """Audit only the validated server pin; never copy arbitrary request context."""
    if SEMANTIC_EXECUTION_CONTEXT_KEY not in request.context:
        return {}
    try:
        snapshot = validate_semantic_execution_request(
            request,
            require_current_versions=True,
        )
    except (TypeError, ValueError):
        # Invalid pins can cause the query failure being audited. Preserve that
        # failure without promoting their claimed versions or execution scope.
        return {"semantic_execution_validation": "invalid"}
    return {
        "semantic_operation": snapshot["operation"],
        "semantic_metric_id": snapshot["metric_id"],
        "semantic_intent": snapshot["intent"],
        "semantic_reason": snapshot["reason"],
        "semantic_reason_code": snapshot["reason_code"],
        "semantic_required_resources": snapshot["required_resources"],
        "semantic_request_scope": snapshot["request_scope"],
        "semantic_ontology_revision": snapshot["ontology_revision"],
        "semantic_binding_revision": snapshot["binding_revision"],
        "semantic_parser_revision": snapshot["parser_revision"],
    }


def _append_envelope_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
) -> None:
    result_meta = envelope.result_meta.model_dump(mode="json")
    if envelope.semantic_context is not None:
        result_meta["semantic_context"] = envelope.semantic_context.model_dump(mode="json")
    result_meta.update(_semantic_query_audit_fields(request))
    _append_audit(
        request=request,
        governance_dir=governance_dir,
        trace_id=envelope.result_meta.trace_id,
        tools_used=_envelope_tools_used(envelope),
        tables_used=list(envelope.evidence.tables_used),
        filters_applied=dict(envelope.evidence.filters_applied),
        result_meta=result_meta,
    )


def _append_failed_query_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    *,
    error: BaseException,
) -> None:
    """本地查询失败审计：与 agent_run_service._build_failed_run_audit_payload 同契约。

    只记录异常类型（error_type），不复制可能含敏感信息的原始错误正文。
    """
    trace_id = f"tr_agent_query_failed_{uuid4().hex[:12]}"
    _append_audit(
        request=request,
        governance_dir=governance_dir,
        trace_id=trace_id,
        tools_used=["agent_query", "provider:local", "status:failed"],
        tables_used=[],
        filters_applied={
            key: value
            for key, value in request.filters.items()
            if _audit_filter_value_present(value)
        },
        result_meta={
            "trace_id": trace_id,
            "basis": request.basis,
            "result_kind": "agent.query_failed",
            "formal_use_allowed": False,
            "quality_flag": "error",
            # Human: caliber-formal_scenario_gate-justified -- this only discloses
            # the already-selected request basis in failed-query metadata; it
            # cannot authorize formal or scenario use.
            "scenario_flag": request.basis == "scenario",
            "provider": "local",
            "error_type": error.__class__.__name__,
            **_semantic_query_audit_fields(request),
        },
    )


def _envelope_tools_used(envelope: AgentEnvelope) -> list[str]:
    """保持既有前两项不变（追加式 JSONL 向后兼容），第三项记录本次真实解析到的 intent。"""
    tools_used = ["analysis_view_tool", "evidence_tool"]
    result_kind = str(envelope.result_meta.result_kind or "").strip()
    intent = result_kind.removeprefix("agent.")
    if intent:
        tools_used.append(f"intent:{intent}")
    return tools_used


def _append_audit(
    *,
    request: AgentQueryRequest,
    governance_dir: str,
    trace_id: str,
    tools_used: list[str],
    tables_used: list[str],
    filters_applied: dict[str, Any],
    result_meta: dict[str, Any],
) -> None:
    append_agent_audit(
        GovernanceRepository(base_dir=governance_dir),
        AgentAuditPayload(
            user_id=str(request.context.get("user_id") or "agent_user"),
            query_text=request.question,
            tools_used=tools_used,
            tables_used=tables_used,
            filters_applied=filters_applied,
            trace_id=trace_id,
            run_id=str(request.context.get("run_id") or "").strip() or None,
            result_meta=result_meta,
        ),
    )


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
    # Preserve structured-filter precedence; only the effective date may be
    # compared with dates explicitly written in the question.
    date_request = AgentQueryRequest(
        question=request.question,
        filters={"report_date": selected} if selected is not None else {},
    )
    report_date, error = _semantic_report_date(date_request, request.question)
    if error is not None:
        raise ValueError(error)
    return report_date


def _coerce_iso_report_date(raw: str) -> str:
    return date.fromisoformat(str(raw).strip()).isoformat()


def _audit_filter_value_present(value: Any) -> bool:
    """审计过滤值保留判定：仅剔除 None 与空串。

    不能写 `value not in (None, "", False)`：Python 中 0 == False，会把
    offset=0 / min_amount=0 这类合法过滤值一并丢弃；0 与 False 都必须保留。
    """
    return not (value is None or value == "")


def _audit_filters(
    request: AgentQueryRequest,
    report_date: str | None,
    *,
    resolution: Literal["explicit", "latest_default", "not_applicable"],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {
        key: value
        for key, value in request.filters.items()
        if _audit_filter_value_present(value)
    }
    if extra:
        for key, value in extra.items():
            if _audit_filter_value_present(value):
                merged[key] = value
    if report_date is not None:
        merged["report_date"] = report_date
    merged["report_date_resolution"] = resolution
    return merged


def _latest_or_requested(request: AgentQueryRequest, available_dates: list[str]) -> str | None:
    requested = _requested_report_date(request)
    if requested is not None:
        normalized = _coerce_iso_report_date(requested)
        if not available_dates:
            raise ValueError("No governed report dates are available for this query.")
        available_normalized = {
            date.fromisoformat(str(d).strip()).isoformat() for d in available_dates
        }
        if normalized not in available_normalized:
            raise ValueError(
                f"Requested report_date={normalized} is not in available governed dates "
                f"{sorted(available_normalized)}."
            )
        return normalized
    if not available_dates:
        return None
    return str(available_dates[0])
