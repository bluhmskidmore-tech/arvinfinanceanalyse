from __future__ import annotations

import importlib
from collections.abc import Callable
from datetime import date
from typing import Any, Literal
from uuid import uuid4

from backend.app.agent.runtime.tool_registry import ToolRegistry
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.governance.agent_audit import AgentAuditPayload, append_agent_audit
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
from backend.app.services.gitnexus_service import build_gitnexus_status_payload

RULE_VERSION = "rv_agent_mvp_v1"
BalanceAnalysisRepository = None


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
    envelope = registry.execute_query(request)
    _append_envelope_audit(request, governance_dir, envelope)
    return envelope


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
        filters_applied={key: value for key, value in request.filters.items() if value not in (None, "")},
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
        "gitnexus_status": lambda request: build_gitnexus_status_payload(request),
        "portfolio_overview": lambda request: _portfolio_overview_payload(request, duckdb_path),
        "pnl_summary": lambda request: _pnl_summary_payload(request, duckdb_path),
        "duration_risk": lambda request: _duration_risk_payload(request, duckdb_path),
        "credit_exposure": lambda request: _credit_exposure_payload(request, duckdb_path),
        "product_pnl": lambda request: _product_pnl_payload(request, duckdb_path),
        "pnl_bridge": lambda request: _pnl_bridge_payload(request, duckdb_path, governance_dir),
        "risk_tensor": lambda request: _risk_tensor_payload(request, duckdb_path, governance_dir),
        "market_data": lambda request: _market_data_payload(request, duckdb_path),
        "news": lambda request: _news_payload(request, duckdb_path),
    }


def _portfolio_overview_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    repo_cls = BalanceAnalysisRepository
    if repo_cls is None:
        repo_cls = getattr(
            importlib.import_module("backend.app.repositories.balance_analysis_repo"),
            "BalanceAnalysisRepository",
        )
    repo = repo_cls(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No balance-analysis report date is available.")
    overview = repo.fetch_formal_overview(
        report_date=report_date,
        position_scope=request.position_scope,
        currency_basis=request.currency_basis,
    )
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    return {
        "answer": (
            f"{report_date} 的组合概览已返回，当前口径共 {overview['detail_row_count']} 条明细，"
            f"总资产规模 {overview['total_market_value_amount']}。"
        ),
        "cards": [
            {"type": "metric", "title": "Total Market Value", "value": str(overview["total_market_value_amount"])},
            {"type": "metric", "title": "Total Amortized Cost", "value": str(overview["total_amortized_cost_amount"])},
            {"type": "metric", "title": "Total Accrued Interest", "value": str(overview["total_accrued_interest_amount"])},
            {"type": "metric", "title": "Detail Rows", "value": str(overview["detail_row_count"])},
        ],
        "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
        "filters_applied": _audit_filters(
            request,
            report_date,
            resolution=rd_mode,
            extra={
                "position_scope": request.position_scope,
                "currency_basis": request.currency_basis,
            },
        ),
        "row_count": int(overview["detail_row_count"]),
        "quality_flag": "ok",
        "basis": "formal",
        "formal_use_allowed": True,
        "scenario_flag": False,
        "source_version": str(overview.get("source_version") or "sv_balance_analysis_unknown"),
        "rule_version": str(overview.get("rule_version") or RULE_VERSION),
        "cache_version": "cv_agent_portfolio_overview_v1",
        "result_kind": "agent.portfolio_overview",
        "vendor_status": "ok",
        "fallback_mode": "none",
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


def _pnl_summary_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    repo = PnlRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_union_report_dates())
    if report_date is None:
        raise ValueError("No PnL report date is available.")
    overview = repo.overview_totals(report_date)
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    return {
        "answer": (
            f"{report_date} 的损益汇总已返回，正式 FI {overview['formal_fi_row_count']} 行，"
            f"非标桥接 {overview['nonstd_bridge_row_count']} 行，总损益 {overview['total_pnl']}。"
        ),
        "cards": [
            {"type": "metric", "title": "Total PnL", "value": str(overview["total_pnl"])},
            {"type": "metric", "title": "Interest 514", "value": str(overview["interest_income_514"])},
            {"type": "metric", "title": "Fair Value 516", "value": str(overview["fair_value_change_516"])},
            {"type": "metric", "title": "Capital Gain 517", "value": str(overview["capital_gain_517"])},
        ],
        "tables_used": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
        "filters_applied": _audit_filters(request, report_date, resolution=rd_mode),
        "row_count": int(overview["formal_fi_row_count"]) + int(overview["nonstd_bridge_row_count"]),
        "quality_flag": "ok",
        "basis": "formal",
        "formal_use_allowed": True,
        "scenario_flag": False,
        "source_version": "sv_agent_pnl_summary",
        "rule_version": RULE_VERSION,
        "cache_version": "cv_agent_pnl_summary_v1",
        "result_kind": "agent.pnl_summary",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "next_drill": [
            {"dimension": "instrument", "label": "按券查看"},
            {"dimension": "portfolio", "label": "按组合查看"},
        ],
        "suggested_actions": [
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
        ],
    }


def _duration_risk_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    repo = BondAnalyticsRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No bond-analytics report date is available.")
    summary = repo.fetch_portfolio_risk_summary(report_date=report_date)
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    return {
        "answer": (
            f"{report_date} 的利率风险摘要已返回，组合久期 {summary['portfolio_duration']}，"
            f"DV01 {summary['portfolio_dv01']}。"
        ),
        "cards": [
            {"type": "metric", "title": "Portfolio Duration", "value": str(summary["portfolio_duration"])},
            {
                "type": "metric",
                "title": "Portfolio Modified Duration",
                "value": str(summary["portfolio_modified_duration"]),
            },
            {"type": "metric", "title": "Portfolio DV01", "value": str(summary["portfolio_dv01"])},
            {"type": "metric", "title": "Portfolio Convexity", "value": str(summary["portfolio_convexity"])},
        ],
        "tables_used": ["fact_formal_bond_analytics_daily"],
        "filters_applied": _audit_filters(request, report_date, resolution=rd_mode),
        "row_count": int(summary.get("bond_count", 0)),
        "quality_flag": "ok",
        "basis": "formal",
        "formal_use_allowed": True,
        "scenario_flag": False,
        "source_version": "sv_agent_duration_risk",
        "rule_version": RULE_VERSION,
        "cache_version": "cv_agent_duration_risk_v1",
        "result_kind": "agent.duration_risk",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "next_drill": [
            {"dimension": "tenor_bucket", "label": "按期限桶查看"},
            {"dimension": "asset_class", "label": "按资产类查看"},
        ],
    }


def _credit_exposure_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    repo = BondAnalyticsRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No bond-analytics report date is available.")
    summary = repo.fetch_credit_summary(report_date=report_date)
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    return {
        "answer": (
            f"{report_date} 的信用暴露摘要已返回，信用债 {summary['credit_bond_count']} 只，"
            f"信用市值 {summary['credit_market_value']}。"
        ),
        "cards": [
            {"type": "metric", "title": "Credit Bond Count", "value": str(summary["credit_bond_count"])},
            {"type": "metric", "title": "Credit Market Value", "value": str(summary["credit_market_value"])},
            {"type": "metric", "title": "Spread DV01", "value": str(summary["spread_dv01"])},
            {"type": "metric", "title": "OCI Credit Exposure", "value": str(summary["oci_credit_exposure"])},
        ],
        "tables_used": ["fact_formal_bond_analytics_daily"],
        "filters_applied": _audit_filters(request, report_date, resolution=rd_mode),
        "row_count": int(summary.get("credit_bond_count", 0)),
        "quality_flag": "ok",
        "basis": "formal",
        "formal_use_allowed": True,
        "scenario_flag": False,
        "source_version": "sv_agent_credit_exposure",
        "rule_version": RULE_VERSION,
        "cache_version": "cv_agent_credit_exposure_v1",
        "result_kind": "agent.credit_exposure",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "next_drill": [
            {"dimension": "issuer", "label": "按发行人查看"},
            {"dimension": "rating", "label": "按评级查看"},
        ],
    }


def _product_pnl_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
    repo = ProductCategoryPnlRepository(duckdb_path)
    report_date = _latest_or_requested(request, repo.list_report_dates())
    if report_date is None:
        raise ValueError("No product-category report date is available.")
    view = str(request.filters.get("view") or "monthly")
    rows = repo.fetch_rows(report_date, view)
    if not rows:
        raise ValueError(f"No product-category rows for report_date={report_date} view={view}.")
    grand_total = next((row for row in rows if str(row.get("category_id")) == "grand_total"), rows[0])
    asset_total = next((row for row in rows if str(row.get("category_id")) == "asset_total"), {})
    liability_total = next((row for row in rows if str(row.get("category_id")) == "liability_total"), {})
    rd_mode: Literal["explicit", "latest_default"] = (
        "explicit" if _requested_report_date(request) else "latest_default"
    )
    return {
        "answer": f"{report_date} 的产品损益视图已返回，当前 view={view}。",
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
        "quality_flag": "ok",
        "basis": "formal",
        "formal_use_allowed": True,
        "scenario_flag": False,
        "source_version": str(rows[0].get("source_version") or repo.latest_source_version()),
        "rule_version": str(rows[0].get("rule_version") or RULE_VERSION),
        "cache_version": "cv_agent_product_pnl_v1",
        "result_kind": "agent.product_pnl",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "next_drill": [{"dimension": "product_category", "label": "按产品分类查看"}],
    }


def _pnl_bridge_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
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
    return {
        "answer": f"{report_date} 的 PnL bridge 已返回。",
        "cards": [
            {"type": "metric", "title": "Explained PnL", "value": str(summary.get("total_explained_pnl", ""))},
            {"type": "metric", "title": "Actual PnL", "value": str(summary.get("total_actual_pnl", ""))},
            {"type": "metric", "title": "Residual", "value": str(summary.get("total_residual", ""))},
        ],
        "tables_used": ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
        "filters_applied": base_filters,
        "row_count": int(summary.get("row_count", 0)),
        "quality_flag": str(meta.get("quality_flag") or "warning"),
        "basis": str(meta.get("basis") or "formal"),
        "formal_use_allowed": bool(meta.get("formal_use_allowed", True)),
        "scenario_flag": bool(meta.get("scenario_flag", False)),
        "source_version": str(meta.get("source_version") or "sv_agent_pnl_bridge"),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta.get("rule_version") or RULE_VERSION),
        "cache_version": str(meta.get("cache_version") or "cv_agent_pnl_bridge_v1"),
        "vendor_status": str(meta.get("vendor_status") or "ok"),
        "fallback_mode": str(meta.get("fallback_mode") or "none"),
        "result_kind": "agent.pnl_bridge",
        "next_drill": [{"dimension": "instrument", "label": "按券桥接查看"}],
    }


def _risk_tensor_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, Any]:
    from backend.app.services.risk_tensor_service import risk_tensor_envelope

    repo = BondAnalyticsRepository(duckdb_path)
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
    return {
        "answer": f"{report_date} 的风险张量已返回。",
        "cards": [
            {"type": "metric", "title": "Portfolio DV01", "value": str(result.get("portfolio_dv01", ""))},
            {"type": "metric", "title": "CS01", "value": str(result.get("cs01", ""))},
            {"type": "metric", "title": "Portfolio Convexity", "value": str(result.get("portfolio_convexity", ""))},
        ],
        "tables_used": ["fact_formal_risk_tensor_daily"],
        "filters_applied": _audit_filters(request, report_date, resolution=rd_mode),
        "row_count": int(result.get("bond_count", 0)),
        "quality_flag": str(meta.get("quality_flag") or "warning"),
        "basis": str(meta.get("basis") or "formal"),
        "formal_use_allowed": bool(meta.get("formal_use_allowed", True)),
        "scenario_flag": bool(meta.get("scenario_flag", False)),
        "source_version": str(meta.get("source_version") or "sv_agent_risk_tensor"),
        "vendor_version": str(meta.get("vendor_version") or "vv_none"),
        "rule_version": str(meta.get("rule_version") or RULE_VERSION),
        "cache_version": str(meta.get("cache_version") or "cv_agent_risk_tensor_v1"),
        "vendor_status": str(meta.get("vendor_status") or "ok"),
        "fallback_mode": str(meta.get("fallback_mode") or "none"),
        "result_kind": "agent.risk_tensor",
        "next_drill": [{"dimension": "krd_bucket", "label": "按KRD桶查看"}],
    }


def _market_data_payload(request: AgentQueryRequest, duckdb_path: str) -> dict[str, Any]:
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


def _append_envelope_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
) -> None:
    _append_audit(
        request=request,
        governance_dir=governance_dir,
        trace_id=envelope.result_meta.trace_id,
        tools_used=["analysis_view_tool", "evidence_tool"],
        tables_used=list(envelope.evidence.tables_used),
        filters_applied=dict(envelope.evidence.filters_applied),
        result_meta=envelope.result_meta.model_dump(mode="json"),
    )


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
            result_meta=result_meta,
        ),
    )


def _requested_report_date(request: AgentQueryRequest) -> str | None:
    current_filters = request.context.get("current_filters")
    if not isinstance(current_filters, dict):
        current_filters = {}
    for key in ("report_date", "date"):
        for container in (request.filters, request.context, current_filters):
            value = container.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _coerce_iso_report_date(raw: str) -> str:
    return date.fromisoformat(str(raw).strip()).isoformat()


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
        if value not in (None, "", False)
    }
    if extra:
        for key, value in extra.items():
            if value not in (None, "", False):
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
