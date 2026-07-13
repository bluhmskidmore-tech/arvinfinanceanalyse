from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from backend.app.api.response_cache import (
    market_home_macro_analysis_cache_key,
    market_home_response_cache,
    market_home_strategy_summaries_cache_key,
)
from backend.app.core_finance.macro import (
    DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
    analyze_cross_market_linkage,
    build_crisis_score_history_payload,
    classify_low_crowding_market_regime,
    clean_low_crowding_observations,
    compute_credit_spread_risk,
    compute_crisis_score_payload,
    compute_economic_cycle,
    compute_leading_indicator,
    compute_liquidity_stress_test,
    compute_low_crowding_scores,
    compute_macro_portfolio_impact,
    compute_monetary_policy_stance,
    compute_rate_turning_point,
    compute_yield_curve_shape,
    generate_random_prices,
    low_crowding_multifactor_selection,
    mean_reversion_momentum_strategy,
    moving_average_strategy,
    multi_factor_selection,
)
from backend.app.core_finance.macro.a_share_stampede_risk import (
    compute_a_share_stampede_risk,
    load_a_share_stampede_risk_config,
)
from backend.app.core_finance.macro.equity_shadow_portfolio import compute_equity_shadow_portfolio_report
from backend.app.core_finance.macro.equity_strategies import REQUIRED_FACTOR_INPUTS
from backend.app.core_finance.macro.helpers import (
    build_curve_history,
    enrich_wide_with_curve_market_fields,
    sort_wide_rows_for_macro,
)
from backend.app.core_finance.macro.macro_portfolio_impact import build_bond_portfolio_profile
from backend.app.core_finance.macro.toolkit import DEFAULT_DATA_SOURCES
from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.core_finance.macro.toolkit.runner import (
    OMITTED_SOURCE_SCRIPTS,
    TOOLKIT_ROOT,
    MacroToolkitScript,
    iter_toolkit_scripts,
)
from backend.app.core_finance.macro.toolkit.system_sources import (
    clear_system_macro_source_cache,
    load_series_by_alias,
    load_series_by_aliases,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import DEFAULT_CFFEX_CONTRACTS, table_stats
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import macro_adversarial_signal_service, macro_toolkit_service
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.tasks.commodity_daily_ingest import COMMODITY_PRODUCTS
from backend.app.tasks.macro_backfill import backfill_macro_series
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ui/macro/toolkit", tags=["macro-toolkit"])

_SOURCE_CHECK_ALIASES = (
    "sh000300",
    "CU0",
    "DR007.IB",
    "M0067855",
    "M0000612",
    "S0059747",
    "S0059749",
    "S0059760",
    "M0041813",
)

_DAILY_SOURCE_CHECK_ALIASES = {
    "sh000300",
    "CU0",
    "DR007.IB",
    "M0067855",
    "S0059747",
    "S0059749",
    "S0059760",
    "M0041813",
}

_SOURCE_BACKFILL_TARGETS = {
    "m0041813": {
        "series_id": "NCD.SHIBOR.3M",
        "series_name": "SHIBOR:3M",
        "default_sources": ["tushare_macro"],
        "backfill_mode": "macro_series",
    },
    "m0041653": {
        "alias": "M0041653",
        "series_id": "EMM00088132",
        "series_name": "公开市场操作:逆回购:7天:中标利率",
        "default_sources": ["choice_edb"],
        "backfill_mode": "crisis_score_inputs",
    },
    "m0017126": {
        "series_id": "M0017126",
        "series_name": "制造业PMI",
        "default_sources": ["tushare_macro"],
        "backfill_mode": "macro_series",
    },
}

_DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS = macro_toolkit_service.DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS
_MACRO_COMMODITY_PRODUCT_CODES = frozenset(spec.product_code.upper() for spec in COMMODITY_PRODUCTS)

_ANALYSIS_INDICATORS = (
    {"key": "hs300", "alias": "sh000300", "label": "沪深300", "unit": "点", "group": "风险资产"},
    {"key": "copper", "alias": "CU0", "label": "铜主力", "unit": "元/吨", "group": "工业需求"},
    {"key": "usdcny", "alias": "M0067855", "label": "美元兑人民币", "unit": "", "group": "汇率"},
    {"key": "dr007", "alias": "DR007.IB", "label": "DR007", "unit": "%", "group": "流动性"},
    {"key": "ncd_3m", "alias": "M0041813", "label": "3M NCD", "unit": "%", "group": "资金利率"},
    {"key": "gov_5y", "alias": "S0059747", "label": "5Y 国债", "unit": "%", "group": "利率"},
    {"key": "gov_10y", "alias": "S0059749", "label": "10Y 国债", "unit": "%", "group": "利率"},
    {"key": "aa_5y", "alias": "S0059760", "label": "5Y AA 信用债", "unit": "%", "group": "信用"},
)

_CAPABILITY_DEFINITIONS = (
    {
        "key": "monetary_policy_stance",
        "legacy_module": "M7",
        "label": "货币政策立场",
        "group": "政策与资金面",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("M0041653", "DR007.IB", "S0059743", "S0059749", "S0059760"),
        "next_step": "封装 /api/macro/monetary-policy-stance，并在本页接入政策立场卡。",
    },
    {
        "key": "yield_curve_shape",
        "legacy_module": "M8",
        "label": "收益率曲线形态",
        "group": "曲线",
        "implementation_status": "partial",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("S0059743", "S0059747", "S0059749"),
        "next_step": "复用正式曲线表，把曲线形态纯函数输出接到宏观工具箱。",
    },
    {
        "key": "credit_spread_risk",
        "legacy_module": "M9",
        "label": "信用利差预警",
        "group": "信用",
        "implementation_status": "partial",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("S0059652", "S0059670", "S0059760"),
        "next_step": "把信用利差风险/分位结果合并到本页信用信号区。",
    },
    {
        "key": "leading_indicator",
        "legacy_module": "M10",
        "label": "宏观领先指标",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("M0017126", "M0001385", "M5525763", "S0059743", "S0059749", "S0059670", "CA.BRENT"),
        "next_step": "补 PMI/M2/社融映射后输出领先指标指数。",
    },
    {
        "key": "liquidity_stress",
        "legacy_module": "M11",
        "label": "流动性压力测试",
        "group": "压力测试",
        "implementation_status": "library_ready",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("DR007.IB", "M0041813"),
        "next_step": "接入资产/负债期限桶，避免只用市场代理指标。",
    },
    {
        "key": "crisis_score_cn",
        "legacy_module": "Crisis",
        "label": "Crisis Score",
        "group": "stress",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("sh000300", "S0059760", "S0059747", "M0067855", "NH0100.NHF", "DR007.IB", "M0041653"),
        "next_step": "Expose the migrated crisis_score_cn model in the macro analysis result cards.",
    },
    {
        "key": "cross_market_linkage",
        "legacy_module": "M12",
        "label": "跨市场联动",
        "group": "联动",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("sh000300", "CU0", "M0067855"),
        "next_step": "把跨资产纯函数输出为联动矩阵和主导变量。",
    },
    {
        "key": "rate_turning_point",
        "legacy_module": "M13",
        "label": "利率拐点判断",
        "group": "曲线",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("DR007.IB", "S0059747", "S0059749"),
        "next_step": "用正式曲线和资金利率输出拐点概率。",
    },
    {
        "key": "economic_cycle",
        "legacy_module": "M14",
        "label": "经济周期定位",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("M0017126", "M0000612", "M0001227", "M0001385", "M5525763"),
        "next_step": "补齐增长/通胀宽表后输出周期象限。",
    },
    {
        "key": "macro_portfolio_impact",
        "legacy_module": "M15",
        "label": "宏观情景组合影响",
        "group": "组合影响",
        "implementation_status": "library_ready",
        "route_status": "partial",
        "frontend_status": "partial",
        "data_aliases": ("S0059749", "S0059760", "M0067855"),
        "next_step": "把组合暴露输入与宏观情景结果合并展示。",
    },
    {
        "key": "decision_summary",
        "legacy_module": "M16",
        "label": "宏观决策摘要",
        "group": "决策摘要",
        "implementation_status": "not_wired",
        "route_status": "not_wired",
        "frontend_status": "planned",
        "data_aliases": ("DR007.IB", "S0059749", "sh000300", "M0067855"),
        "next_step": "聚合 M7-M15 后生成一屏决策摘要，而不是前端拼文案。",
    },
)


class MacroToolkitRunRequest(BaseModel):
    argv: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class MacroToolkitRunChainRequest(BaseModel):
    dry_run: bool = True
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class CffexMemberRankRefreshRequest(BaseModel):
    trade_date: str | None = None
    contracts: list[str] = Field(default_factory=lambda: list(DEFAULT_CFFEX_CONTRACTS))
    sources: list[str] = Field(default_factory=lambda: ["choice", "tushare"])


class ChoiceStockRefreshRequest(BaseModel):
    as_of_date: str | None = None
    refresh_history: bool = True
    refresh_factors: bool = True
    factor_max_stock_count: int | None = Field(default=None, ge=1)
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off"


class SourceBackfillRefreshRequest(BaseModel):
    alias: str = Field(min_length=1)
    start_date: str | None = None
    end_date: str | None = None
    sources: list[str] | None = None


class CommodityFuturesRefreshRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    products: list[str] | None = None
    dry_run: bool = False


@router.get("/scripts")
def macro_toolkit_scripts(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    scripts = [_script_payload(script) for script in iter_toolkit_scripts()]
    source_checks = _source_checks(settings.duckdb_path)
    source_check_cache = {str(check["alias"]): check for check in source_checks}
    cffex_status = _cffex_member_rank_status(
        settings.duckdb_path,
        reference_date=_latest_source_check_date(source_checks),
    )
    commodity_permission = _commodity_futures_refresh_permission_payload(auth, settings=settings)
    commodity_status = _commodity_futures_status(settings.duckdb_path)
    readiness = macro_toolkit_service.macro_model_readiness(
        output_dir=OUTPUT_DIR,
        reference_date=_latest_source_check_date(source_checks),
    )
    return _envelope(
        "macro_toolkit.scripts",
        {
            "default_data_sources": list(DEFAULT_DATA_SOURCES),
            "toolkit_root": str(TOOLKIT_ROOT),
            "output_dir": str(OUTPUT_DIR),
            "scripts": scripts,
            "groups": sorted({str(item["group"]) for item in scripts}),
            "omitted_scripts": OMITTED_SOURCE_SCRIPTS,
            "output_files": _output_files(),
            "source_checks": source_checks,
            "capabilities": _capability_plan(
                settings.duckdb_path,
                source_check_cache=source_check_cache,
            ),
            "cffex_member_rank": cffex_status,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                reference_date=_latest_source_check_date(source_checks),
            ),
            "commodity_futures_refresh": {
                "permission": commodity_permission,
                "status": commodity_status,
            },
            "model_readiness": readiness["model_readiness"],
            "readiness_summary": readiness["readiness_summary"],
            "warnings": _script_warnings(cffex_status),
        },
    )


@router.get("/analysis")
def macro_toolkit_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    detail: Annotated[str, Query(pattern="^(full|core)$")] = "full",
    history_limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    resolved_history_limit = history_limit or DEFAULT_CRISIS_SCORE_HISTORY_LIMIT
    return market_home_response_cache.get_or_build(
        market_home_macro_analysis_cache_key(
            settings.duckdb_path,
            detail,
            history_limit=resolved_history_limit if detail == "full" else None,
        ),
        lambda: _build_macro_toolkit_analysis(detail, history_limit=resolved_history_limit),
    )


def _build_macro_toolkit_analysis(detail: str, *, history_limit: int = DEFAULT_CRISIS_SCORE_HISTORY_LIMIT) -> dict[str, object]:
    settings = get_settings()
    indicators = _analysis_indicators(settings.duckdb_path)
    indicator_by_key = {str(item["key"]): item for item in indicators}
    output_files = _output_files()
    analysis_date = _latest_indicator_date(indicators)
    readiness = macro_toolkit_service.macro_model_readiness(
        output_dir=OUTPUT_DIR,
        reference_date=analysis_date,
    )
    if detail == "core":
        a_share_risk = None
        capability_results: list[dict[str, object]] = []
        strategy_summaries: list[dict[str, object]] = []
        source_checks: list[dict[str, object]] = []
        capabilities: list[dict[str, object]] = []
        runtime_status = _analysis_runtime_status("core")
    else:
        a_share_risk, capability_results, strategy_summaries = _build_macro_toolkit_full_analysis_blocks(
            settings.duckdb_path,
            analysis_date,
            history_limit=history_limit,
        )
        source_check_cache: dict[str, dict[str, object]] = {}
        _source_checks_for_aliases(
            (
                str(alias)
                for aliases in (
                    _SOURCE_CHECK_ALIASES,
                    tuple(
                        str(alias)
                        for definition in _CAPABILITY_DEFINITIONS
                        for alias in definition["data_aliases"]
                    ),
                )
                for alias in aliases
            ),
            settings.duckdb_path,
            source_check_cache=source_check_cache,
        )
        source_checks = _source_checks(settings.duckdb_path, source_check_cache=source_check_cache)
        capabilities = _capability_plan(settings.duckdb_path, source_check_cache=source_check_cache)
        runtime_status = _analysis_runtime_status("full")
    signal_cards = _analysis_signal_cards(
        indicator_by_key,
        output_files,
        capability_results,
        a_share_risk,
        capabilities_deferred=detail == "core",
    )
    hason_strategy = _hason_macro_strategy_summary(output_files, analysis_date=analysis_date)
    hit_count = sum(1 for item in indicators if item["latest_value"] is not None)
    coverage = {
        "indicator_count": len(indicators),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(indicators), 4) if indicators else 0,
        "script_count": len(iter_toolkit_scripts()),
        "output_file_count": len(output_files),
    }
    conclusion = _analysis_conclusion(signal_cards, coverage)
    warnings = _analysis_warnings(coverage)
    data_health = _analysis_data_health(
        indicators=indicators,
        source_checks=source_checks,
        capability_results=capability_results,
        capabilities=capabilities,
        runtime_status=runtime_status,
        warnings=warnings,
        reference_date=analysis_date,
    )
    return _envelope(
        "macro_toolkit.analysis",
        {
            "default_data_sources": list(DEFAULT_DATA_SOURCES),
            "as_of_date": analysis_date,
            "conclusion": conclusion,
            "coverage": coverage,
            "indicators": indicators,
            "signal_cards": signal_cards,
            "hason_strategy": hason_strategy,
            "a_share_risk": a_share_risk,
            "capability_results": capability_results,
            "strategy_summaries": strategy_summaries,
            "output_files": output_files,
            "source_checks": source_checks,
            "capabilities": capabilities,
            "cffex_member_rank": _cffex_member_rank_status(
                settings.duckdb_path,
                reference_date=_latest_indicator_date(indicators),
            ),
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                reference_date=analysis_date,
            ),
            "runtime_status": runtime_status,
            "data_health": data_health,
            "model_readiness": readiness["model_readiness"],
            "readiness_summary": readiness["readiness_summary"],
            "warnings": warnings,
        },
    )


def _build_macro_toolkit_full_analysis_blocks(
    duckdb_path: str | Path,
    analysis_date: date,
    *,
    history_limit: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    with ThreadPoolExecutor(max_workers=3) as executor:
        a_share_risk_future = executor.submit(_a_share_stampede_risk, duckdb_path)
        capability_results_future = executor.submit(
            lambda: _macro_capability_results(
                duckdb_path,
                report_date=analysis_date,
                history_limit=history_limit,
            )
        )
        strategy_summaries_future = executor.submit(_equity_strategy_summaries, duckdb_path)
        return (
            a_share_risk_future.result(),
            capability_results_future.result(),
            strategy_summaries_future.result(),
        )


@router.get("/analysis/strategy-summaries")
def macro_toolkit_strategy_summaries(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    return market_home_response_cache.get_or_build(
        market_home_strategy_summaries_cache_key(settings.duckdb_path),
        _build_macro_toolkit_strategy_summaries,
    )


def _build_macro_toolkit_strategy_summaries() -> dict[str, object]:
    settings = get_settings()
    strategies, price_context = _equity_strategy_summaries_with_context(settings.duckdb_path)
    shadow_portfolio_report = compute_equity_shadow_portfolio_report(
        settings.duckdb_path,
        latest_factor_snapshot=_latest_factor_snapshot_from_price_context(price_context),
    )
    return _envelope(
        "macro_toolkit.analysis.strategy_summaries",
        {
            "strategy_summaries": strategies,
            "shadow_portfolio_report": shadow_portfolio_report,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                reference_date=_latest_strategy_as_of_date(strategies),
            ),
        },
    )


@router.get("/adversarial-signal")
def macro_toolkit_adversarial_signal(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_macro_toolkit_read_allowed(auth, get_settings())
    payload, meta = macro_adversarial_signal_service.load_macro_adversarial_signal_payload(
        output_dir=OUTPUT_DIR
    )
    return build_result_envelope(
        basis="analytical",
        trace_id=f"macro-toolkit-adversarial-signal-{uuid.uuid4().hex[:12]}",
        result_kind="macro_toolkit.adversarial_signal",
        cache_version="cv_macro_adversarial_signal_v1",
        source_version=str(meta.get("source_version") or "macro_toolkit.adversarial_signal.missing"),
        rule_version="rv_macro_adversarial_signal_v1",
        result_payload=payload,
        quality_flag=str(meta.get("quality_flag") or "warning"),
        vendor_version=str(meta.get("vendor_version") or "macro_toolkit.local_csv"),
        vendor_status=str(meta.get("vendor_status") or "vendor_unavailable"),
        fallback_mode=str(meta.get("fallback_mode") or "none"),
        tables_used=list(meta.get("tables_used") or []),
        evidence_rows=int(meta.get("evidence_rows") or 0),
        as_of_date=str(meta.get("as_of_date")) if meta.get("as_of_date") else None,
    )


@router.post("/cffex-member-rank/refresh")
def macro_toolkit_refresh_cffex_member_rank(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: CffexMemberRankRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or CffexMemberRankRefreshRequest()
    settings = get_settings()
    _ensure_cffex_member_rank_refresh_allowed(auth, settings)
    refresh = macro_toolkit_service.refresh_cffex_member_rank(
        duckdb_path=settings.duckdb_path,
        trade_date=refresh_request.trade_date,
        contracts=tuple(refresh_request.contracts or DEFAULT_CFFEX_CONTRACTS),
        sources=tuple(refresh_request.sources or ["choice", "tushare"]),
    )
    return _envelope(
        "macro_toolkit.cffex_member_rank_refresh",
        {
            "refresh": refresh.payload,
            "cffex_member_rank": _cffex_member_rank_status(settings.duckdb_path),
        },
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.post("/choice-stock/refresh")
def macro_toolkit_refresh_choice_stock(
    background_tasks: BackgroundTasks,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request: ChoiceStockRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or ChoiceStockRefreshRequest()
    if (
        not refresh_request.refresh_history
        and not refresh_request.refresh_factors
        and refresh_request.theme_overlay_mode == "off"
    ):
        raise HTTPException(
            status_code=400,
            detail=("At least one of refresh_history, refresh_factors, or theme_overlay_mode must request work."),
        )

    settings = get_settings()
    _ensure_choice_stock_refresh_allowed(auth, settings)
    as_of_date = refresh_request.as_of_date or _default_choice_stock_refresh_as_of_date(settings.duckdb_path)
    permission = _choice_stock_refresh_permission_payload(auth)
    try:
        refresh = macro_toolkit_service.queue_choice_stock_refresh(
            background_tasks=background_tasks,
            duckdb_path=str(settings.duckdb_path),
            catalog_path=str(settings.choice_stock_catalog_file),
            governance_path=str(settings.governance_path),
            archive_root=str(settings.local_archive_path),
            as_of_date=as_of_date,
            refresh_history=refresh_request.refresh_history,
            refresh_factors=refresh_request.refresh_factors,
            factor_max_stock_count=refresh_request.factor_max_stock_count,
            theme_overlay_mode=refresh_request.theme_overlay_mode,
            permission=permission,
            idempotency_key=idempotency_key,
        )
    except macro_toolkit_service.MacroToolkitConflictError:
        raise HTTPException(
            status_code=409,
            detail=f"Choice stock refresh already in progress for as_of_date={as_of_date}.",
        ) from None
    return _envelope(
        "macro_toolkit.choice_stock_refresh",
        {
            "refresh": refresh.payload,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                permission=permission,
                reference_date=refresh.as_of_date,
            ),
        },
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.get("/choice-stock/refresh-status")
def macro_toolkit_choice_stock_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(default=""),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        status = _choice_stock_refresh_status(settings.governance_path, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _envelope(
        "macro_toolkit.choice_stock_refresh_status",
        {
            "refresh": status,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                reference_date=str(status.get("report_date") or "")[:10] or None,
            ),
        },
    )


@router.post("/source-backfill/refresh")
def macro_toolkit_refresh_source_backfill(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: SourceBackfillRefreshRequest,
) -> dict[str, object]:
    settings = get_settings()
    _ensure_source_backfill_refresh_allowed(auth, settings)
    target = _source_backfill_target(request.alias)
    start_date = request.start_date or _default_source_backfill_start_date(request.end_date)
    end_date = request.end_date or date.today().isoformat()
    try:
        payload = _execute_source_backfill(
            target=target,
            alias=request.alias,
            duckdb_path=str(settings.duckdb_path),
            start_date=start_date,
            end_date=end_date,
            sources_filter=request.sources or list(target["default_sources"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload_status = str(payload.get("status") or "").strip()
    refresh_status = payload_status or ("completed" if not payload.get("errors") else "partial")
    total_added = int(payload.get("total_added") or 0)
    refresh = {
        "status": refresh_status,
        "alias": request.alias,
        "series_ids": [str(target["series_id"])],
        "series_names": [str(target["series_name"])],
        "start_date": start_date,
        "end_date": end_date,
        "total_added": total_added,
        "total_fetched": int(payload.get("total_fetched") or 0),
        "processed_count": int(payload.get("processed_count") or 0),
        "results": payload.get("results") or {},
        "errors": payload.get("errors") or {},
        "run_id": payload.get("run_id"),
        "source_by_series": payload.get("source_by_series") or {},
        "vendor_versions": payload.get("vendor_versions") or {},
    }
    if total_added > 0:
        market_home_response_cache.invalidate()
        clear_system_macro_source_cache()
    return _envelope(
        "macro_toolkit.source_backfill_refresh",
        {"refresh": refresh},
        quality_flag="ok" if refresh_status == "completed" else "warning",
        fallback_mode="none",
        as_of_date=end_date,
    )


@router.post("/commodity-futures/refresh")
def macro_toolkit_refresh_commodity_futures(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: CommodityFuturesRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or CommodityFuturesRefreshRequest()
    settings = get_settings()
    _ensure_commodity_futures_refresh_allowed(auth, settings)
    permission = _commodity_futures_refresh_permission_payload(auth, allowed=True)
    end_date = refresh_request.end_date or date.today().isoformat()
    start_date = refresh_request.start_date or _default_source_backfill_start_date(end_date)
    products = _macro_commodity_refresh_products(refresh_request.products)
    before_status = _commodity_futures_status(settings.duckdb_path)
    try:
        refresh = macro_toolkit_service.refresh_commodity_futures(
            start_date=start_date,
            end_date=end_date,
            duckdb_path=str(settings.duckdb_path),
            products=products,
            dry_run=refresh_request.dry_run,
            permission=permission,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    status = str(refresh.payload.get("status") or "")
    after_status = before_status
    summary = _commodity_futures_refresh_summary(
        before_status=before_status,
        after_status=after_status,
        dry_run=refresh_request.dry_run,
    )
    refresh_payload = {
        **refresh.payload,
        "before_status": before_status,
        "after_status": after_status,
        "summary": summary,
    }
    if not refresh_request.dry_run and status == "completed":
        market_home_response_cache.invalidate()
        clear_system_macro_source_cache()
    return _envelope(
        "macro_toolkit.commodity_futures_refresh",
        {
            "refresh": refresh_payload,
            "commodity_futures_refresh": {
                "permission": permission,
                "refresh": refresh_payload,
                "status": after_status,
            },
        },
        quality_flag=refresh.quality_flag if status == "queued" else ("ok" if status == "dry_run" else "warning"),
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date or end_date,
    )


def _macro_commodity_refresh_products(products: list[str] | None) -> tuple[str, ...]:
    requested = list(_DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS) if products is None else products
    normalized = tuple(str(product).strip().upper() for product in requested)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="At least one commodity futures product is required.",
        )
    unknown = tuple(product for product in normalized if product not in _MACRO_COMMODITY_PRODUCT_CODES)
    if unknown:
        unknown_labels = ", ".join(product or "<blank>" for product in unknown)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown commodity futures product: {unknown_labels}.",
        )
    return normalized


@router.post("/scripts/{name}/run")
def macro_toolkit_run(
    name: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: MacroToolkitRunRequest | None = None,
) -> dict[str, object]:
    run_request = request or MacroToolkitRunRequest()
    settings = get_settings()
    _ensure_macro_toolkit_script_execute_allowed(auth, settings, script_name=name)
    if run_request.argv:
        raise HTTPException(
            status_code=400,
            detail="Script arguments are not allowed for HTTP macro toolkit runs.",
        )
    try:
        return macro_toolkit_service.run_macro_toolkit_script(
            name=name,
            argv=run_request.argv,
            timeout_seconds=run_request.timeout_seconds,
            output_dir=OUTPUT_DIR,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scripts/run-chain")
def macro_toolkit_run_chain(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: MacroToolkitRunChainRequest | None = None,
) -> dict[str, object]:
    run_request = request or MacroToolkitRunChainRequest()
    settings = get_settings()
    _ensure_macro_toolkit_script_execute_allowed(auth, settings, script_name="macro_toolkit_chain")
    source_checks = _source_checks(settings.duckdb_path)
    try:
        payload = macro_toolkit_service.run_macro_toolkit_chain(
            dry_run=run_request.dry_run,
            timeout_seconds=run_request.timeout_seconds,
            output_dir=OUTPUT_DIR,
            reference_date=_latest_source_check_date(source_checks),
            governance_path=settings.governance_path,
            authorize_script=lambda script_name: _ensure_macro_toolkit_script_execute_allowed(
                auth,
                settings,
                script_name=script_name,
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not run_request.dry_run:
        market_home_response_cache.invalidate()
    return _envelope(
        "macro_toolkit.script_chain_run",
        {"run": payload, "model_readiness": payload["model_readiness"]},
        quality_flag="ok" if str(payload.get("status")) in {"completed", "dry_run"} else "warning",
        fallback_mode="none",
        as_of_date=None,
    )


def _ensure_macro_toolkit_read_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_cffex_member_rank_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.cffex_member_rank",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_choice_stock_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.choice_stock",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_source_backfill_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.source_backfill",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_commodity_futures_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.commodity_futures",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_macro_toolkit_script_execute_allowed(
    auth: AuthContext,
    settings: object,
    *,
    script_name: str,
) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.script",
            action="execute",
            scope_key="script",
            scope_value=script_name,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _source_backfill_target(alias: str) -> dict[str, object]:
    key = str(alias or "").strip().lower()
    target = _SOURCE_BACKFILL_TARGETS.get(key)
    if target is None:
        raise HTTPException(status_code=400, detail=f"Unsupported macro source backfill alias: {alias}")
    return target


def _execute_source_backfill(
    *,
    target: dict[str, object],
    alias: str,
    duckdb_path: str,
    start_date: str,
    end_date: str,
    sources_filter: list[str] | None,
) -> dict[str, object]:
    mode = str(target.get("backfill_mode") or "macro_series")
    if mode == "crisis_score_inputs":
        from backend.scripts.backfill_crisis_score_inputs import backfill_crisis_score_inputs

        backfill_alias = str(target.get("alias") or alias)
        payload = backfill_crisis_score_inputs(
            duckdb_path=duckdb_path,
            start_date=start_date,
            end_date=end_date,
            dry_run=False,
            aliases=[backfill_alias],
        )
        result = (payload.get("results") or {}).get(backfill_alias) or {}
        total_added = int(result.get("written_rows") or result.get("row_count") or 0)
        return {
            "dry_run": False,
            "processed_count": 0 if payload.get("errors") else 1,
            "total_added": total_added,
            "results": {backfill_alias: total_added},
            "errors": payload.get("errors") or {},
        }
    return backfill_macro_series(
        duckdb_path=duckdb_path,
        series_names=[str(target["series_name"])],
        start_date=start_date,
        end_date=end_date,
        dry_run=False,
        sources_filter=sources_filter,
    )


def _default_source_backfill_start_date(end_date: str | None) -> str:
    try:
        end = date.fromisoformat(str(end_date)[:10]) if end_date else date.today()
    except ValueError:
        end = date.today()
    return (end - timedelta(days=31)).isoformat()


def _script_payload(script: MacroToolkitScript) -> dict[str, object]:
    return {
        "name": script.name,
        "filename": script.filename,
        "group": script.group,
        "default_data_sources": list(script.default_data_sources),
        "optional_dependencies": list(script.optional_dependencies),
        "notes": script.notes,
        "path": str(script.path.relative_to(TOOLKIT_ROOT)),
        "available": script.path.exists(),
    }


def _output_files() -> list[dict[str, object]]:
    return macro_toolkit_service.output_files(OUTPUT_DIR)


def _source_checks(
    duckdb_path: str | Path,
    *,
    source_check_cache: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    return _source_checks_for_aliases(
        _SOURCE_CHECK_ALIASES,
        duckdb_path,
        source_check_cache=source_check_cache,
    )


def _source_checks_for_aliases(
    aliases: Iterable[str],
    duckdb_path: str | Path,
    *,
    source_check_cache: dict[str, dict[str, object]] | None = None,
    end: str | None = None,
    frames_by_alias: dict[str, pd.DataFrame] | None = None,
) -> list[dict[str, object]]:
    cache = source_check_cache if source_check_cache is not None else {}
    requested_aliases = tuple(dict.fromkeys(str(alias) for alias in aliases))
    missing_aliases = tuple(alias for alias in requested_aliases if alias not in cache)
    if missing_aliases:
        loaded_frames_by_alias = frames_by_alias or {}
        aliases_to_load = tuple(alias for alias in missing_aliases if alias not in loaded_frames_by_alias)
        if aliases_to_load:
            loaded_frames_by_alias = {
                **loaded_frames_by_alias,
                **load_series_by_aliases(aliases_to_load, end=end, duckdb_path=duckdb_path),
            }
        for alias in missing_aliases:
            cache[alias] = _source_check_payload(alias, loaded_frames_by_alias[alias])
    return [cache[alias] for alias in requested_aliases]


def _source_check(alias: str, duckdb_path: str | Path, *, end: str | None = None) -> dict[str, object]:
    frame = load_series_by_alias(alias, end=end, duckdb_path=duckdb_path)
    return _source_check_payload(alias, frame)


def _source_check_payload(alias: str, frame: pd.DataFrame) -> dict[str, object]:
    latest = None
    if not frame.empty:
        latest_row = frame.sort_values("date").iloc[-1]
        latest = {
            "date": str(latest_row["date"])[:10],
            "series_id": str(latest_row["series_id"]),
            "vendor_name": str(latest_row["vendor_name"]),
            "value": float(latest_row["value"]),
        }
    return {"alias": alias, "row_count": int(len(frame)), "latest": latest}


def _latest_source_check_date(checks: list[dict[str, object]]) -> str | None:
    dates = [
        str(latest["date"])
        for check in checks
        if isinstance((latest := check.get("latest")), dict) and latest.get("date")
    ]
    return max(dates) if dates else None


def _cffex_member_rank_status(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    stats = table_stats(duckdb_path)
    latest_trade_date = str(stats.get("latest_trade_date") or "")[:10] or None
    return {
        **stats,
        **_cffex_freshness(latest_trade_date, reference_date),
    }


def _cffex_freshness(latest_trade_date: str | None, reference_date: str | None) -> dict[str, object]:
    if not latest_trade_date:
        return {
            "freshness_status": "missing",
            "reference_date": reference_date,
            "stale_days": None,
        }
    if not reference_date:
        return {
            "freshness_status": "unknown",
            "reference_date": None,
            "stale_days": None,
        }
    try:
        latest = date.fromisoformat(latest_trade_date[:10])
        reference = date.fromisoformat(reference_date[:10])
    except ValueError:
        return {
            "freshness_status": "unknown",
            "reference_date": reference_date,
            "stale_days": None,
        }
    stale_days = (reference - latest).days
    if stale_days <= 1:
        status = "current"
    elif stale_days <= 7:
        status = "lagging"
    else:
        status = "stale"
    return {
        "freshness_status": status,
        "reference_date": reference.isoformat(),
        "stale_days": stale_days,
    }


def _script_warnings(cffex_status: dict[str, object]) -> list[str]:
    if cffex_status.get("freshness_status") == "stale":
        latest = cffex_status.get("latest_trade_date") or "缺失"
        reference = cffex_status.get("reference_date") or "当前分析日"
        stale_days = cffex_status.get("stale_days")
        return [
            f"中金所席位排名已落库但最新交易日 {latest}，落后宏观分析日 {reference} {stale_days} 天；"
            "可使用刷新席位补齐 Choice/Tushare 数据。"
        ]
    if int(cffex_status.get("row_count") or 0) > 0:
        return []
    if cffex_status.get("materialized") is True:
        return ["中金所席位排名表已创建但暂无数据；运行 CFFEX refresh 后可用 Choice/Tushare 补齐。"]
    return ["中金所席位排名表尚未初始化；运行 CFFEX refresh 会创建正式表并用 Choice/Tushare 补齐。"]


def _append_choice_stock_refresh_run(governance_path: str | Path, payload: dict[str, object]) -> None:
    macro_toolkit_service.append_choice_stock_refresh_run(governance_path, payload)


def _choice_stock_refresh_run_payload(
    *,
    run_id: str,
    status: str,
    as_of_date: str,
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    refresh_history: bool = True,
    refresh_factors: bool = True,
    factor_max_stock_count: int | None = None,
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off",
    theme_overlay_status: str | None = None,
    theme_overlay_message: str | None = None,
    theme_overlay_member_count: int | None = None,
    theme_overlay_run_id: str | None = None,
    history_row_count: int | None = None,
    factor_row_count: int | None = None,
    source_version: object | None = None,
    vendor_version: object | None = None,
    error_message: str | None = None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
    permission: dict[str, object] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    return macro_toolkit_service.build_choice_stock_refresh_run_payload(
        run_id=run_id,
        status=status,
        as_of_date=as_of_date,
        queued_at=queued_at,
        started_at=started_at,
        finished_at=finished_at,
        refresh_history=refresh_history,
        refresh_factors=refresh_factors,
        factor_max_stock_count=factor_max_stock_count,
        theme_overlay_mode=theme_overlay_mode,
        theme_overlay_status=theme_overlay_status,
        theme_overlay_message=theme_overlay_message,
        theme_overlay_member_count=theme_overlay_member_count,
        theme_overlay_run_id=theme_overlay_run_id,
        history_row_count=history_row_count,
        factor_row_count=factor_row_count,
        source_version=source_version,
        vendor_version=vendor_version,
        error_message=error_message,
        failure_category=failure_category,
        failure_reason=failure_reason,
        permission=permission,
        idempotency_key=idempotency_key,
    )


def _choice_stock_refresh_status(
    governance_path: str | Path,
    *,
    run_id: str = "",
) -> dict[str, object]:
    return macro_toolkit_service.choice_stock_refresh_status(governance_path, run_id=run_id)


def _latest_choice_stock_inflight_refresh(
    governance_path: str | Path,
    *,
    as_of_date: str,
) -> dict[str, object] | None:
    return macro_toolkit_service.latest_choice_stock_inflight_refresh(
        governance_path,
        as_of_date=as_of_date,
    )


def _choice_stock_refresh_permission_payload(auth: AuthContext | None = None) -> dict[str, object]:
    return macro_toolkit_service.build_choice_stock_refresh_permission_payload(auth)


def _commodity_futures_refresh_permission_payload(
    auth: AuthContext | None = None,
    *,
    settings: object | None = None,
    allowed: bool | None = None,
) -> dict[str, object]:
    resolved_allowed = allowed
    if resolved_allowed is None and auth is not None and settings is not None:
        try:
            ensure_user_allowed(
                auth=auth,
                settings=settings,
                resource="macro_toolkit.commodity_futures",
                action="refresh",
            )
            resolved_allowed = True
        except PermissionError:
            resolved_allowed = False
        except RuntimeError:
            resolved_allowed = None
    return macro_toolkit_service.build_commodity_futures_refresh_permission_payload(
        auth,
        allowed=resolved_allowed,
    )


def _commodity_futures_status(duckdb_path: str | Path) -> dict[str, object]:
    return macro_toolkit_service.commodity_futures_status(duckdb_path)


def _commodity_futures_refresh_summary(
    *,
    before_status: dict[str, object],
    after_status: dict[str, object],
    dry_run: bool,
) -> dict[str, object]:
    before_coverage = before_status.get("coverage") if isinstance(before_status.get("coverage"), dict) else {}
    after_coverage = after_status.get("coverage") if isinstance(after_status.get("coverage"), dict) else {}
    before_available = _commodity_status_text_set(before_coverage.get("available_products"))
    after_available = _commodity_status_text_set(after_coverage.get("available_products"))
    newly_available_products = after_available - before_available
    before_nanhua = before_status.get("nanhua_input") if isinstance(before_status.get("nanhua_input"), dict) else {}
    after_nanhua = after_status.get("nanhua_input") if isinstance(after_status.get("nanhua_input"), dict) else {}
    before_row_count = _commodity_status_int(before_status.get("row_count"))
    after_row_count = _commodity_status_int(after_status.get("row_count"))
    return {
        "table": str(after_status.get("table") or before_status.get("table") or "fact_commodity_futures_daily"),
        "row_count_before": before_row_count,
        "row_count_after": after_row_count,
        "row_count_delta": (
            after_row_count - before_row_count
            if before_row_count is not None and after_row_count is not None
            else None
        ),
        "latest_trade_date_before": before_status.get("latest_trade_date"),
        "latest_trade_date_after": after_status.get("latest_trade_date"),
        "available_product_count_before": _commodity_status_int(before_coverage.get("available_product_count")),
        "available_product_count_after": _commodity_status_int(after_coverage.get("available_product_count")),
        "target_product_count": _commodity_status_int(after_coverage.get("target_product_count"))
        or _commodity_status_int(before_coverage.get("target_product_count")),
        "newly_available_products": _commodity_ordered_products(newly_available_products),
        "missing_products_after": _commodity_ordered_products(
            _commodity_status_text_set(after_coverage.get("missing_products"))
        ),
        "nanhua_status_before": before_nanhua.get("status"),
        "nanhua_status_after": after_nanhua.get("status"),
        "nanhua_latest_date_before": before_nanhua.get("latest_trade_date"),
        "nanhua_latest_date_after": after_nanhua.get("latest_trade_date"),
        "nanhua_latest_value_after": after_nanhua.get("latest_value"),
        "source_vendors_after": sorted(_commodity_status_text_set(after_status.get("source_vendors"))),
        "dry_run": dry_run,
    }


def _commodity_status_text_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _commodity_ordered_products(products: set[str]) -> list[str]:
    ordered = [product for product in _DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS if product in products]
    ordered.extend(sorted(product for product in products if product not in set(ordered)))
    return ordered


def _commodity_status_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _choice_stock_refresh_overview(
    duckdb_path: str | Path,
    governance_path: str | Path,
    *,
    permission: dict[str, object] | None = None,
    reference_date: str | None = None,
) -> dict[str, object]:
    return macro_toolkit_service.choice_stock_refresh_overview(
        duckdb_path,
        governance_path,
        permission=permission,
        reference_date=reference_date,
    )


def _default_choice_stock_refresh_as_of_date(duckdb_path: str | Path) -> str:
    return macro_toolkit_service.default_choice_stock_refresh_as_of_date(duckdb_path)


def _capability_plan(
    duckdb_path: str | Path,
    *,
    source_check_cache: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    cache = source_check_cache if source_check_cache is not None else {}
    _source_checks_for_aliases(
        (
            str(alias)
            for definition in _CAPABILITY_DEFINITIONS
            for alias in definition["data_aliases"]
        ),
        duckdb_path,
        source_check_cache=cache,
    )
    return [_capability_payload(item, duckdb_path, source_check_cache=cache) for item in _CAPABILITY_DEFINITIONS]


def _capability_payload(
    definition: dict[str, object],
    duckdb_path: str | Path,
    *,
    source_check_cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in definition["data_aliases"])
    checks: list[dict[str, object]] = []
    for alias in aliases:
        if alias not in source_check_cache:
            source_check_cache[alias] = _source_check(alias, duckdb_path)
        checks.append(source_check_cache[alias])
    hit_count = sum(1 for check in checks if check["latest"])
    required_count = len(checks)
    if required_count == 0:
        data_status = "not_required"
    elif hit_count == required_count:
        data_status = "ready"
    elif hit_count > 0:
        data_status = "partial"
    else:
        data_status = "missing"
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_status": data_status,
        "data_hit_count": hit_count,
        "data_required_count": required_count,
        "evidence": [
            {
                "alias": check["alias"],
                "row_count": check["row_count"],
                "latest_date": check["latest"]["date"] if check["latest"] else None,
                "series_id": check["latest"]["series_id"] if check["latest"] else None,
            }
            for check in checks
        ],
        "next_step": "已在本页输出结构化结果；下一步沉淀为正式宏观端点和页面契约。",
    }


_CURVE_TYPE_TO_ID = {
    "treasury": "CN_GOVT",
    "cdb": "CN_CDB",
    "aaa_credit": "CN_CREDIT_AAA",
    "aa_plus_credit": "CN_CREDIT_AA_PLUS",
    "aa_credit": "CN_CREDIT_AA",
}

_CURVE_ALIAS_POINTS = (
    ("S0059743", "CN_GOVT", "1Y"),
    ("S0059746", "CN_GOVT", "3Y"),
    ("S0059747", "CN_GOVT", "5Y"),
    ("S0059748", "CN_GOVT", "7Y"),
    ("S0059749", "CN_GOVT", "10Y"),
    ("S0059752", "CN_GOVT", "30Y"),
    ("S0059650", "CN_CREDIT_AAA", "1Y"),
    ("S0059651", "CN_CREDIT_AAA", "3Y"),
    ("S0059652", "CN_CREDIT_AAA", "5Y"),
    ("S0059653", "CN_CREDIT_AA_PLUS", "1Y"),
    ("S0059654", "CN_CREDIT_AA_PLUS", "3Y"),
    ("S0059655", "CN_CREDIT_AA_PLUS", "5Y"),
    ("S0059656", "CN_CREDIT_AA", "1Y"),
    ("S0059657", "CN_CREDIT_AA", "3Y"),
    ("S0059760", "CN_CREDIT_AA", "5Y"),
    ("DR007.IB", "CN_DR", "7D"),
    ("M0041653", "CN_RRP", "7D"),
    ("M0041813", "CN_SHIBOR", "3M"),
)

_WIDE_SERIES_ALIASES = (
    ("hs300", "sh000300"),
    ("copper", "CU0"),
    ("usdcny", "M0067855"),
    ("fx_usdcny", "M0067855"),
    ("brent_oil", "CA.BRENT"),
    ("pmi", "M0017126"),
    ("cpi_yoy", "M0000612"),
    ("ppi_yoy", "M0001227"),
    ("m2_yoy", "M0001385"),
    ("social_financing_yoy", "M5525763"),
    ("industrial_yoy", "M0000545"),
    ("credit_spread_aaa_3y", "S0059670"),
    ("dr007", "DR007.IB"),
)

_CRISIS_SCORE_INPUTS = (
    {"field": "hs300", "label": "HS300 close", "alias": "sh000300", "warning": "HS300_MISSING"},
    {"field": "aa_5y", "label": "AA credit yield 5Y", "alias": "S0059760", "warning": "AA_5Y_MISSING"},
    {"field": "gov_5y", "label": "Treasury yield 5Y", "alias": "S0059747", "warning": "GOV_5Y_MISSING"},
    {"field": "usdcny", "label": "USD/CNY", "alias": "M0067855", "warning": "USDCNY_MISSING"},
    {"field": "nanhua", "label": "Nanhua commodity index", "alias": "NH0100.NHF", "warning": "NANHUA_MISSING"},
    {"field": "dr007", "label": "DR007", "alias": "DR007.IB", "warning": "DR007_MISSING"},
    {
        "field": "reverse_repo_7d",
        "label": "7D reverse repo",
        "alias": "M0041653",
        "warning": "REVERSE_REPO_7D_MISSING",
    },
)

_CRISIS_COMMODITY_COVERAGE_INPUTS = (
    {"field": "rebar", "label": "Rebar futures", "aliases": ("RB0", "RB0.SHF")},
    {"field": "iron_ore", "label": "Iron ore futures", "aliases": ("I0", "I0.DCE")},
    {"field": "copper", "label": "Copper futures", "aliases": ("CU0", "CU0.SHF")},
    {"field": "aluminum", "label": "Aluminum futures", "aliases": ("AL0", "AL0.SHF")},
    {"field": "crude_oil", "label": "Crude oil futures", "aliases": ("SC0", "SC0.INE")},
    {"field": "gold", "label": "Gold futures", "aliases": ("AU0", "AU0.SHF")},
)
_CRISIS_COMMODITY_FIELD_TO_PRODUCT = {
    "rebar": "RB",
    "iron_ore": "I",
    "copper": "CU",
    "aluminum": "AL",
    "crude_oil": "SC",
    "gold": "AU",
}
_CRISIS_COMMODITY_SHADOW_MIN_SAMPLES = 20
_CRISIS_COMMODITY_SHADOW_FORMULA_VERSION = "rv_macro_crisis_score_shadow_commodity_v1"
_CRISIS_COMMODITY_SHADOW_WEIGHT = 0.05
_CRISIS_COMMODITY_ADMISSION_RULE_VERSION = "rv_macro_crisis_commodity_admission_v1"
_CRISIS_COMMODITY_APPROVAL_PACK_VERSION = "rv_macro_crisis_commodity_approval_pack_v1"
_CRISIS_COMMODITY_ADMISSION_MIN_CRISIS_SAMPLES = 5
_CRISIS_COMMODITY_ADMISSION_MIN_CORRELATION = 0.2

_CAPABILITY_INPUT_REQUIREMENTS = {
    "monetary_policy_stance": (
        {
            "field": "policy_rate_7d",
            "label": "Policy rate 7D",
            "aliases": ("M0041653",),
            "warning": "POLICY_RATE_7D_MISSING",
            "required": True,
        },
        {
            "field": "dr007",
            "label": "DR007",
            "aliases": ("DR007.IB",),
            "warning": "DR007_MISSING",
            "required": True,
        },
        {
            "field": "gov_10y",
            "label": "Treasury 10Y",
            "aliases": ("S0059749",),
            "warning": "GOV_10Y_MISSING",
            "required": False,
        },
    ),
    "leading_indicator": (
        {
            "field": "pmi",
            "label": "PMI",
            "aliases": ("M0017126",),
            "warning": "PMI_MISSING",
            "required": True,
        },
        {
            "field": "m2_yoy",
            "label": "M2 YoY",
            "aliases": ("M0001385",),
            "warning": "M2_YOY_MISSING",
            "required": True,
        },
        {
            "field": "social_financing_yoy",
            "label": "Social financing YoY",
            "aliases": ("M5525763",),
            "warning": "SOCIAL_FINANCING_YOY_MISSING",
            "required": True,
        },
        {
            "field": "term_spread_10y_1y",
            "label": "10Y-1Y term spread",
            "aliases": ("S0059743", "S0059749"),
            "warning": "TERM_SPREAD_MISSING",
            "required": True,
            "derived": True,
        },
        {
            "field": "credit_spread_aaa_3y",
            "label": "AAA credit spread",
            "aliases": ("S0059670",),
            "warning": "CREDIT_SPREAD_AAA_MISSING",
            "required": True,
            "derived": True,
        },
        {
            "field": "brent_oil",
            "label": "Brent oil",
            "aliases": ("CA.BRENT",),
            "warning": "COMMODITY_MISSING",
            "required": True,
        },
    ),
    "economic_cycle": (
        {
            "field": "pmi",
            "label": "PMI",
            "aliases": ("M0017126",),
            "warning": "PMI_MISSING",
            "required": True,
        },
        {
            "field": "cpi_yoy",
            "label": "CPI YoY",
            "aliases": ("M0000612",),
            "warning": "CPI_YOY_MISSING",
            "required": True,
        },
        {
            "field": "ppi_yoy",
            "label": "PPI YoY",
            "aliases": ("M0001227",),
            "warning": "PPI_YOY_MISSING",
            "required": True,
        },
        {
            "field": "m2_yoy",
            "label": "M2 YoY",
            "aliases": ("M0001385",),
            "warning": "M2_YOY_MISSING",
            "required": True,
        },
        {
            "field": "social_financing_yoy",
            "label": "Social financing YoY",
            "aliases": ("M5525763",),
            "warning": "SOCIAL_FINANCING_YOY_MISSING",
            "required": True,
        },
    ),
}


def _macro_capability_results(
    duckdb_path: str | Path,
    *,
    report_date: str | None,
    history_limit: int = DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
) -> list[dict[str, object]]:
    parsed_report_date = _parse_report_date(report_date)
    if parsed_report_date is None:
        crisis_report_date = _latest_crisis_input_date(duckdb_path)
        return [
            _crisis_score_card_without_analysis_date(item, duckdb_path, crisis_report_date)
            if item["key"] == "crisis_score_cn"
            else _unavailable_capability_result(item, "缺少可用分析日期")
            for item in _CAPABILITY_DEFINITIONS
        ]

    curve_rows = _load_macro_curve_rows(duckdb_path, parsed_report_date)
    report_date_frames_by_alias = load_series_by_aliases(
        tuple(
            dict.fromkeys(
                [
                    *(alias for _, alias in _WIDE_SERIES_ALIASES),
                    *(
                        str(alias)
                        for requirements in _CAPABILITY_INPUT_REQUIREMENTS.values()
                        for requirement in requirements
                        for alias in requirement.get("aliases", ())
                    ),
                ]
            )
        ),
        end=parsed_report_date.isoformat(),
        duckdb_path=duckdb_path,
    )
    wide_rows = _load_macro_wide_rows(
        duckdb_path,
        parsed_report_date,
        curve_rows,
        frames_by_alias=report_date_frames_by_alias,
    )
    risk_tensor = _load_latest_risk_tensor_row(duckdb_path, parsed_report_date)
    proxy_rows, bucket_rows, total_assets = _risk_tensor_to_liquidity_inputs(risk_tensor)
    positions = _load_latest_bond_positions(duckdb_path, parsed_report_date)
    portfolio_profile = build_bond_portfolio_profile(positions, parsed_report_date)
    current_curve = _current_gov_curve(curve_rows, parsed_report_date)

    raw_results: dict[str, dict[str, object]] = {
        "monetary_policy_stance": _run_capability(
            "monetary_policy_stance",
            lambda: compute_monetary_policy_stance(curve_rows, report_date=parsed_report_date),
        ),
        "yield_curve_shape": _run_capability(
            "yield_curve_shape",
            lambda: compute_yield_curve_shape(curve_rows, report_date=parsed_report_date),
        ),
        "credit_spread_risk": _run_capability(
            "credit_spread_risk",
            lambda: compute_credit_spread_risk(curve_rows, report_date=parsed_report_date),
        ),
        "leading_indicator": _run_capability(
            "leading_indicator",
            lambda: compute_leading_indicator(wide_rows, parsed_report_date),
        ),
        "liquidity_stress": _run_capability(
            "liquidity_stress",
            lambda: compute_liquidity_stress_test(
                proxy_rows,
                bucket_rows,
                report_date=parsed_report_date,
                total_assets=total_assets,
            ),
        ),
        "crisis_score_cn": _run_capability(
            "crisis_score_cn",
            lambda: _compute_crisis_score_capability(
                duckdb_path,
                parsed_report_date,
                history_limit=history_limit,
            ),
        ),
        "cross_market_linkage": _run_capability(
            "cross_market_linkage",
            lambda: analyze_cross_market_linkage(wide_rows, parsed_report_date),
        ),
        "rate_turning_point": _run_capability(
            "rate_turning_point",
            lambda: compute_rate_turning_point(curve_rows, report_date=parsed_report_date),
        ),
        "economic_cycle": _run_capability(
            "economic_cycle",
            lambda: compute_economic_cycle(wide_rows, parsed_report_date),
        ),
        "macro_portfolio_impact": _run_capability(
            "macro_portfolio_impact",
            lambda: compute_macro_portfolio_impact(
                portfolio_profile,
                current_curve,
                parsed_report_date,
            ),
        ),
    }
    input_evidence_source_check_cache: dict[str, dict[str, object]] = {}
    _source_checks_for_aliases(
        (
            str(alias)
            for requirements in _CAPABILITY_INPUT_REQUIREMENTS.values()
            for requirement in requirements
            for alias in requirement.get("aliases", ())
        ),
        duckdb_path,
        source_check_cache=input_evidence_source_check_cache,
        end=parsed_report_date.isoformat(),
        frames_by_alias=report_date_frames_by_alias,
    )
    for key in ("monetary_policy_stance", "leading_indicator", "economic_cycle"):
        raw_results[key] = _with_capability_input_evidence(
            key,
            raw_results[key],
            duckdb_path=duckdb_path,
            report_date=parsed_report_date,
            wide_rows=wide_rows,
            source_check_cache=input_evidence_source_check_cache,
            source_frames_by_alias=report_date_frames_by_alias,
        )

    cards: list[dict[str, object]] = []
    for definition in _CAPABILITY_DEFINITIONS:
        if definition["key"] == "decision_summary":
            cards.append(_decision_summary_card(definition, cards, parsed_report_date))
            continue
        raw_result = raw_results.get(str(definition["key"]))
        cards.append(_capability_result_card(definition, raw_result))
    return cards


_EQUITY_STRATEGY_PRICE_CONTEXT_UNSET = object()


def _equity_strategy_summaries_with_context(
    duckdb_path: str | Path | None = None,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    try:
        price_context = _load_equity_strategy_price_context(duckdb_path)
        return _equity_strategy_summaries(duckdb_path, price_context=price_context), price_context
    except Exception as exc:  # pragma: no cover - displayed as unavailable strategy evidence
        return [_unavailable_equity_strategy_summary(exc)], None


def _latest_factor_snapshot_from_price_context(price_context: dict[str, object] | None) -> pd.DataFrame | None:
    if not isinstance(price_context, dict):
        return None
    financials = price_context.get("financials")
    if isinstance(financials, pd.DataFrame) and not financials.empty:
        return financials
    return None


def _equity_strategy_summaries(
    duckdb_path: str | Path | None = None,
    *,
    price_context: object = _EQUITY_STRATEGY_PRICE_CONTEXT_UNSET,
) -> list[dict[str, object]]:
    try:
        if price_context is _EQUITY_STRATEGY_PRICE_CONTEXT_UNSET:
            price_context = _load_equity_strategy_price_context(duckdb_path)
        if price_context is not None:
            return _real_equity_strategy_summaries(price_context)
        prices = generate_random_prices(num_stocks=4, num_days=180, seed=20260506)
        moving_average = moving_average_strategy(prices)
        mean_reversion = mean_reversion_momentum_strategy(prices)
        financials = pd.DataFrame(
            {
                "pe": [8.0, 18.0, 35.0, 12.0],
                "pb": [0.8, 2.2, 4.0, 1.5],
                "ps": [1.0, 3.0, 8.0, 2.0],
                "roe": [0.22, 0.12, 0.03, 0.18],
                "gross_margin": [0.45, 0.30, 0.08, 0.38],
                "three_month_return": [0.18, 0.08, -0.12, 0.12],
                "twelve_month_return": [0.42, 0.10, -0.30, 0.24],
                "volatility": [0.16, 0.25, 0.45, 0.20],
                "dividend_yield": [0.06, 0.03, 0.00, 0.04],
                "industry": ["technology", "consumer", "technology", "financial"],
            },
            index=["AAA", "BBB", "CCC", "DDD"],
        )
        selected = multi_factor_selection(financials, top_pct=0.5, industries_focus=["technology"])
        sample_prices = prices.copy()
        sample_prices.columns = financials.index
        sample_observations = _sample_strategy_observations(sample_prices)
        low_crowding_selected = low_crowding_multifactor_selection(
            financials,
            sample_observations,
            top_pct=0.5,
        )
        low_crowding_regime = classify_low_crowding_market_regime(sample_prices, sample_observations)
        return [
            _strategy_summary(
                key="moving_average",
                label="移动均线策略",
                metric_label="样例累计净值",
                metric_value=round(float(moving_average.iloc[-1]), 4),
                evidence=[
                    "短均线上穿长均线时建仓，下穿或触发止损时退出。",
                    f"合成价格样本 {len(prices)} 个观察点。",
                ],
                result={"final_value": round(float(moving_average.iloc[-1]), 6)},
            ),
            _strategy_summary(
                key="mean_reversion_momentum",
                label="均值回归 + 动量",
                metric_label="样例累计净值",
                metric_value=round(float(mean_reversion.iloc[-1]), 4),
                evidence=[
                    "低于均值的价格偏离需同时站上趋势均线才进入观察。",
                    f"合成价格样本 {len(prices)} 个观察点。",
                ],
                result={"final_value": round(float(mean_reversion.iloc[-1]), 6)},
            ),
            _strategy_summary(
                key="multi_factor_selection",
                label="多因子选股",
                metric_label="样例入选数量",
                metric_value=int(len(selected)),
                evidence=[
                    "价值、质量、动量、低波和股息因子标准化后加权排序。",
                    f"样例池 {len(financials)} 只，聚焦 technology 行业。",
                ],
                result={
                    "selected_symbols": [str(symbol) for symbol in selected.index.tolist()],
                    "top_score": round(float(selected["score"].iloc[0]), 6) if not selected.empty else None,
                },
            ),
            _strategy_summary(
                key="low_crowding_regime_multifactor",
                label="低拥挤度择时多因子",
                metric_label="样例目标仓位",
                metric_value=low_crowding_regime["target_position"],
                evidence=[
                    f"样例市场状态 {low_crowding_regime['regime']}，仅用于模块可用性检查。",
                    f"样例低拥挤多因子入选 {len(low_crowding_selected)} 只。",
                ],
                result={
                    "regime": low_crowding_regime["regime"],
                    "target_position": low_crowding_regime["target_position"],
                    "selected_symbols": [str(symbol) for symbol in low_crowding_selected.index.tolist()],
                    "selection_top_pct": 0.5,
                },
            ),
        ]
    except Exception as exc:  # pragma: no cover - displayed as unavailable strategy evidence
        return [_unavailable_equity_strategy_summary(exc)]


def _unavailable_equity_strategy_summary(exc: Exception) -> dict[str, object]:
    return {
        "key": "equity_strategies",
        "label": "A股策略模块",
        "group": "A股策略",
        "status": "unavailable",
        "tone": "missing",
        "primary_metric": None,
        "evidence": [],
        "warnings": [f"{type(exc).__name__}: {exc}"],
        "result": {"data_status": "unavailable"},
    }


def _a_share_stampede_risk(duckdb_path: str | Path | None) -> dict[str, object]:
    config = load_a_share_stampede_risk_config()
    context = _load_a_share_stampede_risk_context(duckdb_path)
    if context is None:
        return compute_a_share_stampede_risk(pd.DataFrame(), config=config)
    payload = compute_a_share_stampede_risk(
        context["observations"],
        config=config,
        theme_frame=context.get("theme_frame") if isinstance(context.get("theme_frame"), pd.DataFrame) else None,
    )
    tables_used = [str(item) for item in context.get("tables_used", [])]
    payload["tables_used"] = _unique_texts([*payload.get("tables_used", []), *tables_used])
    if context.get("warnings"):
        payload["warnings"] = _unique_texts([*payload.get("warnings", []), *context["warnings"]])
        if payload.get("status") == "complete":
            payload["status"] = "degraded"
    return payload


def _load_a_share_stampede_risk_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    return macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)


def _real_equity_strategy_summaries(price_context: dict[str, object]) -> list[dict[str, object]]:
    prices = price_context["prices"]
    if not isinstance(prices, pd.DataFrame):
        return []

    moving_average = moving_average_strategy(prices)
    mean_reversion = mean_reversion_momentum_strategy(prices)
    financials = price_context.get("financials")
    common_result = {
        "data_status": "complete",
        "price_source": "choice_stock_daily_observation",
        "as_of_date": price_context["as_of_date"],
        "stock_count": len(prices.columns),
        "observation_count": len(prices.index),
        "tables_used": price_context["tables_used"],
        "source_versions": price_context["source_versions"],
        "vendor_versions": price_context["vendor_versions"],
    }
    return [
        _strategy_summary(
            key="moving_average",
            label="移动均线策略",
            metric_label="真实累计净值",
            metric_value=round(float(moving_average.iloc[-1]), 4),
            status="complete",
            warnings=[],
            evidence=[
                "短均线上穿长均线时建仓，下穿或触发止损时退出。",
                f"已接入 choice_stock_daily_observation，样本 {len(prices.columns)} 只股票、{len(prices.index)} 个交易日。",
            ],
            result={"final_value": round(float(moving_average.iloc[-1]), 6), **common_result},
        ),
        _strategy_summary(
            key="mean_reversion_momentum",
            label="均值回归 + 动量",
            metric_label="真实累计净值",
            metric_value=round(float(mean_reversion.iloc[-1]), 4),
            status="complete",
            warnings=[],
            evidence=[
                "低于均值的价格偏离需同时站上趋势均线才进入观察。",
                f"已接入 choice_stock_daily_observation，最新交易日 {price_context['as_of_date']}。",
            ],
            result={"final_value": round(float(mean_reversion.iloc[-1]), 6), **common_result},
        ),
        _real_multi_factor_summary(price_context, prices=prices, financials=financials),
        _real_low_crowding_regime_multifactor_summary(
            price_context,
            prices=prices,
            financials=financials,
        ),
    ]


def _real_multi_factor_summary(
    price_context: dict[str, object],
    *,
    prices: pd.DataFrame,
    financials: object,
) -> dict[str, object]:
    if isinstance(financials, pd.DataFrame) and not financials.empty:
        selected = multi_factor_selection(financials)
        selected_stock_codes = [str(stock_code) for stock_code in selected.index.tolist()]
        factor_provenance = _factor_snapshot_provenance(financials)
        factor_as_of_date = _factor_snapshot_as_of_date(financials)
        factor_date_status = _factor_snapshot_date_status(financials)
        warnings = _factor_snapshot_date_warnings(factor_date_status)
        return {
            "key": "multi_factor_selection",
            "label": "多因子选股",
            "group": "A股策略",
            "status": "complete",
            "tone": "neutral",
            "primary_metric": {"label": "真实入选数量", "value": len(selected), "unit": ""},
            "evidence": [
                "已接入 choice_stock_factor_snapshot，按估值、质量、动量、低波动、股息五类因子打分。",
                f"因子快照日 {factor_as_of_date or price_context['as_of_date']}，行情日 {price_context['as_of_date']}，可用股票 {len(financials.index)} 只。",
            ],
            "warnings": warnings,
            "result": {
                "data_status": "complete",
                "price_source": "choice_stock_daily_observation",
                "factor_source": "choice_stock_factor_snapshot",
                "as_of_date": price_context["as_of_date"],
                "factor_as_of_date": factor_as_of_date,
                "factor_date_status": factor_date_status,
                "stock_count": len(prices.columns),
                "factor_row_count": len(financials.index),
                "selected_count": len(selected),
                "selected_stock_codes": selected_stock_codes,
                "selection_top_pct": 0.1,
                "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
                "source_versions": price_context["source_versions"],
                "vendor_versions": price_context["vendor_versions"],
                **factor_provenance,
            },
        }
    return {
        "key": "multi_factor_selection",
        "label": "多因子选股",
        "group": "A股策略",
        "status": "degraded",
        "tone": "neutral",
        "primary_metric": None,
        "evidence": [
            "A股价格与行业数据已接入系统表，可用于行情类策略。",
            "PE/PB/ROE/股息率等基本面因子尚未落库，未执行原多因子选股。",
        ],
        "warnings": ["FUNDAMENTAL_FACTORS_NOT_MATERIALIZED"],
        "result": {
            "data_status": "degraded",
            "price_source": "choice_stock_daily_observation",
            "as_of_date": price_context["as_of_date"],
            "stock_count": len(prices.columns),
            "missing_factor_inputs": list(REQUIRED_FACTOR_INPUTS),
            "tables_used": price_context["tables_used"],
            "source_versions": price_context["source_versions"],
            "vendor_versions": price_context["vendor_versions"],
        },
    }


def _real_low_crowding_regime_multifactor_summary(
    price_context: dict[str, object],
    *,
    prices: pd.DataFrame,
    financials: object,
) -> dict[str, object]:
    observations = price_context.get("observations")
    if not isinstance(observations, pd.DataFrame) or observations.empty:
        return {
            "key": "low_crowding_regime_multifactor",
            "label": "低拥挤度择时多因子",
            "group": "A股策略",
            "status": "unavailable",
            "tone": "missing",
            "primary_metric": None,
            "evidence": [],
            "warnings": ["CHOICE_STOCK_OBSERVATIONS_NOT_MATERIALIZED"],
            "result": {"data_status": "unavailable"},
        }

    clean_observations = clean_low_crowding_observations(observations)
    crowding_scores = compute_low_crowding_scores(observations, clean_observations=clean_observations)
    regime = classify_low_crowding_market_regime(prices, observations, clean_observations=clean_observations)
    base_result = {
        "data_status": "complete",
        "price_source": "choice_stock_daily_observation",
        "as_of_date": price_context["as_of_date"],
        "regime": regime["regime"],
        "target_position": regime["target_position"],
        "regime_score": regime["regime_score"],
        "breadth_score": regime["breadth_score"],
        "limit_down_count": regime["limit_down_count"],
        "amount_change_20": regime["amount_change_20"],
        "idx_ret_20d": regime["idx_ret_20d"],
        "stock_count": len(prices.columns),
        "observation_count": len(prices.index),
        "tables_used": price_context["tables_used"],
        "source_versions": price_context["source_versions"],
        "vendor_versions": price_context["vendor_versions"],
    }
    if not isinstance(financials, pd.DataFrame) or financials.empty:
        return {
            "key": "low_crowding_regime_multifactor",
            "label": "低拥挤度择时多因子",
            "group": "A股策略",
            "status": "degraded",
            "tone": "neutral",
            "primary_metric": {"label": "目标仓位", "value": regime["target_position"], "unit": ""},
            "evidence": [
                f"市场状态 {regime['regime']}，仓位建议 {regime['target_position']}。",
                "因子快照缺失，未执行低拥挤多因子选股。",
            ],
            "warnings": ["FACTOR_SNAPSHOT_REQUIRED_FOR_LOW_CROWDING_MULTIFACTOR"],
            "result": {
                **base_result,
                "data_status": "degraded",
                "missing_factor_inputs": list(REQUIRED_FACTOR_INPUTS),
            },
        }

    selected = low_crowding_multifactor_selection(
        financials,
        observations,
        crowding_scores=crowding_scores,
    )
    selected_stock_codes = [str(stock_code) for stock_code in selected.index.tolist()]
    factor_provenance = _factor_snapshot_provenance(financials)
    factor_as_of_date = _factor_snapshot_as_of_date(financials)
    factor_date_status = _factor_snapshot_date_status(financials)
    warnings = _factor_snapshot_date_warnings(factor_date_status)
    excluded_count = (
        int(selected["crowding_excluded_count"].iloc[0])
        if "crowding_excluded_count" in selected.columns and not selected.empty
        else 0
    )
    return {
        "key": "low_crowding_regime_multifactor",
        "label": "低拥挤度择时多因子",
        "group": "A股策略",
        "status": "complete",
        "tone": "neutral",
        "primary_metric": {"label": "目标仓位", "value": regime["target_position"], "unit": ""},
        "evidence": [
            f"市场状态 {regime['regime']}，仓位建议 {regime['target_position']}。",
            f"因子快照 {factor_as_of_date or price_context['as_of_date']}，行情日 {price_context['as_of_date']}，低拥挤多因子入选 {len(selected_stock_codes)} 只。",
        ],
        "warnings": warnings,
        "result": {
            **base_result,
            "factor_source": "choice_stock_factor_snapshot",
            "factor_as_of_date": factor_as_of_date,
            "factor_date_status": factor_date_status,
            "factor_row_count": len(financials.index),
            "selected_count": len(selected_stock_codes),
            "selected_stock_codes": selected_stock_codes,
            "selection_top_pct": 0.1,
            "crowding_excluded_count": excluded_count,
            "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
            **factor_provenance,
        },
    }


def _load_equity_strategy_price_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    return macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)


def _load_equity_strategy_factor_snapshot(
    duckdb_path: Path,
    as_of_date: str,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame | None:
    return macro_toolkit_service.load_equity_strategy_factor_snapshot(
        duckdb_path,
        as_of_date,
        stock_codes=stock_codes,
    )


def _factor_snapshot_provenance(financials: pd.DataFrame) -> dict[str, list[str]]:
    provenance = financials.attrs.get("provenance")
    if not isinstance(provenance, dict):
        return {}
    return {
        key: [str(item) for item in values if str(item or "").strip()]
        for key, values in provenance.items()
        if key.startswith("factor_") and isinstance(values, list) and values
    }


def _factor_snapshot_as_of_date(financials: pd.DataFrame) -> str | None:
    text = str(financials.attrs.get("factor_as_of_date") or "").strip()
    return text or None


def _factor_snapshot_date_status(financials: pd.DataFrame) -> str:
    text = str(financials.attrs.get("factor_date_status") or "").strip()
    return text or "unknown"


def _factor_snapshot_date_warnings(factor_date_status: str) -> list[str]:
    if factor_date_status == "fallback":
        return ["FACTOR_SNAPSHOT_DATE_FALLBACK"]
    return []


def _sample_strategy_observations(prices: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    returns = prices.pct_change().fillna(0.0) * 100
    for trade_date in prices.index:
        for stock_code in prices.columns:
            close = float(prices.loc[trade_date, stock_code])
            pctchange = float(returns.loc[trade_date, stock_code])
            rows.append(
                {
                    "trade_date": trade_date,
                    "stock_code": str(stock_code),
                    "close_value": close,
                    "amount": close * 100_000.0,
                    "pctchange": pctchange,
                    "turn": 1.0 + abs(pctchange) * 0.05,
                    "amplitude": abs(pctchange) * 0.5,
                    "highlimit": close * 1.1,
                    "lowlimit": close * 0.9,
                }
            )
    return pd.DataFrame(rows)


def _unique_texts(values: list[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _strategy_summary(
    *,
    key: str,
    label: str,
    metric_label: str,
    metric_value: int | float,
    evidence: list[str],
    result: dict[str, object],
    status: str = "sample_only",
    warnings: list[str] | None = None,
) -> dict[str, object]:
    resolved_warnings = ["SYNTHETIC_SAMPLE_ONLY"] if warnings is None else warnings
    data_status = str(result.get("data_status") or status)
    return {
        "key": key,
        "label": label,
        "group": "A股策略",
        "status": status,
        "tone": "neutral",
        "primary_metric": {"label": metric_label, "value": metric_value, "unit": ""},
        "evidence": evidence,
        "warnings": resolved_warnings,
        "result": {"data_status": data_status, **result},
    }


def _compute_crisis_score_capability(
    duckdb_path: str | Path,
    report_date: date,
    *,
    history_limit: int = DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
) -> dict[str, object]:
    start = report_date - timedelta(days=420)
    crisis_aliases = tuple(str(config["alias"]) for config in _CRISIS_SCORE_INPUTS)
    commodity_aliases = tuple(
        str(alias)
        for config in _CRISIS_COMMODITY_COVERAGE_INPUTS
        for alias in config["aliases"]
    )
    frames_by_alias = load_series_by_aliases(
        (*crisis_aliases, *commodity_aliases),
        start=start.isoformat(),
        end=report_date.isoformat(),
        duckdb_path=duckdb_path,
    )
    series_data: dict[str, list[tuple[date, float]]] = {}
    inputs: list[dict[str, object]] = []
    for config in _CRISIS_SCORE_INPUTS:
        alias = str(config["alias"])
        frame = frames_by_alias[alias]
        points = _frame_to_crisis_points(frame)
        field = str(config["field"])
        series_data[field] = points
        latest = frame.sort_values("date").iloc[-1] if not frame.empty else None
        latest_date = str(latest["date"])[:10] if latest is not None else None
        latest_value = _float_or_none(latest["value"]) if latest is not None else None
        inputs.append(
            {
                "field": field,
                "label": str(config["label"]),
                "aliases": [alias],
                "warning": str(config["warning"]),
                "required": True,
                "available": bool(points),
                "row_count": int(len(frame)),
                "latest_date": latest_date,
                "series_id": str(latest["series_id"]) if latest is not None else None,
                "source": str(latest["vendor_name"]) if latest is not None else None,
                "value": latest_value,
            }
        )

    result = compute_crisis_score_payload(series_data, report_date=report_date)
    crisis_history = _crisis_score_history(series_data, report_date)
    missing_inputs = [
        str(item["warning"])
        for item in inputs
        if item["required"] and not item["available"]
    ]
    warnings = [str(item) for item in result.get("warnings", []) if item]
    for warning in missing_inputs:
        if warning not in warnings:
            warnings.append(warning)
    enriched = dict(result)
    enriched["warnings"] = warnings
    if missing_inputs and str(enriched.get("data_status") or "").lower() == "complete":
        enriched["data_status"] = "degraded"
    enriched["input_evidence"] = {
        "inputs": inputs,
        "missing_inputs": missing_inputs,
        "sources": _unique_sorted_texts(item.get("source") for item in inputs),
        "latest_dates": _unique_sorted_texts(item.get("latest_date") for item in inputs),
    }
    commodity_coverage = _crisis_commodity_coverage(
        duckdb_path,
        report_date=report_date,
        start=start,
        crisis_history=crisis_history,
        frames_by_alias=frames_by_alias,
    )
    enriched["commodity_coverage"] = commodity_coverage
    enriched["shadow_impact"] = _crisis_commodity_shadow_impact(
        current_score=_float_or_none(enriched.get("crisis_score")),
        coverage=commodity_coverage,
    )
    commodity_admission = _crisis_commodity_candidate_admission(
        coverage=commodity_coverage,
    )
    enriched["commodity_candidate_admission"] = commodity_admission
    enriched["commodity_candidate_approval_pack"] = _crisis_commodity_candidate_approval_pack(
        admission=commodity_admission,
        shadow_impact=enriched["shadow_impact"],
    )
    enriched["score_history"] = build_crisis_score_history_payload(crisis_history, limit=history_limit)
    return enriched


def _crisis_commodity_coverage(
    duckdb_path: str | Path,
    *,
    report_date: date,
    start: date,
    crisis_history: pd.DataFrame,
    frames_by_alias: dict[str, pd.DataFrame] | None = None,
) -> dict[str, object]:
    resolved_frames_by_alias = frames_by_alias
    if resolved_frames_by_alias is None:
        resolved_frames_by_alias = load_series_by_aliases(
            tuple(str(alias) for config in _CRISIS_COMMODITY_COVERAGE_INPUTS for alias in config["aliases"]),
            start=start.isoformat(),
            end=report_date.isoformat(),
            duckdb_path=duckdb_path,
        )
    items = [
        _crisis_commodity_coverage_item(
            config,
            duckdb_path=duckdb_path,
            report_date=report_date,
            start=start,
            crisis_history=crisis_history,
            frames_by_alias=resolved_frames_by_alias,
        )
        for config in _CRISIS_COMMODITY_COVERAGE_INPUTS
    ]
    available_count = sum(1 for item in items if item["available"])
    candidate_summary = _crisis_commodity_candidate_summary(items)
    return {
        "role": "supplemental_observation",
        "tracked_count": len(items),
        "available_count": available_count,
        "missing_inputs": [str(item["field"]) for item in items if not item["available"]],
        "sources": _unique_sorted_texts(item.get("source") for item in items),
        "latest_dates": _unique_sorted_texts(item.get("latest_date") for item in items),
        "used_in_crisis_score": ["nanhua"],
        "candidate_summary": candidate_summary,
        "items": items,
    }


def _crisis_commodity_coverage_item(
    config: dict[str, object],
    *,
    duckdb_path: str | Path,
    report_date: date,
    start: date,
    crisis_history: pd.DataFrame,
    frames_by_alias: dict[str, pd.DataFrame] | None = None,
) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in config["aliases"])
    matched_alias = None
    frame = pd.DataFrame()
    for alias in aliases:
        candidate = (
            frames_by_alias[alias]
            if frames_by_alias is not None
            else load_series_by_alias(
                alias,
                start=start.isoformat(),
                end=report_date.isoformat(),
                duckdb_path=duckdb_path,
            )
        )
        if not candidate.empty:
            matched_alias = alias
            frame = candidate
            break
    latest = frame.sort_values("date").iloc[-1] if not frame.empty else None
    latest_date = str(latest["date"])[:10] if latest is not None else None
    date_alignment_status = (
        "missing" if latest_date is None else "aligned" if latest_date == report_date.isoformat() else "lagging"
    )
    return {
        "field": str(config["field"]),
        "label": str(config["label"]),
        "aliases": list(aliases),
        "matched_alias": matched_alias,
        "role": "supplemental_observation",
        "used_in_formula": False,
        "available": latest is not None,
        "row_count": int(len(frame)),
        "latest_date": latest_date,
        "report_date": report_date.isoformat(),
        "date_alignment_status": date_alignment_status,
        "series_id": str(latest["series_id"]) if latest is not None else None,
        "source": str(latest["vendor_name"]) if latest is not None else None,
        "value": _float_or_none(latest["value"]) if latest is not None else None,
        "candidate_decision": _crisis_commodity_candidate_decision(
            available=latest is not None,
            date_alignment_status=date_alignment_status,
        ),
        "shadow_evaluation": _crisis_commodity_shadow_evaluation(frame, crisis_history),
    }


def _crisis_commodity_candidate_summary(items: list[dict[str, object]]) -> dict[str, object]:
    statuses = [
        str(decision.get("status") or "")
        for item in items
        if isinstance(decision := item.get("candidate_decision"), dict)
    ]
    shadow_statuses = [
        str(shadow.get("status") or "")
        for item in items
        if isinstance(shadow := item.get("shadow_evaluation"), dict)
    ]
    shadow_ready_count = shadow_statuses.count("review_ready")
    shadow_short_count = shadow_statuses.count("history_short")
    shadow_short_items = [
        {
            "field": str(item.get("field") or ""),
            "label": str(item.get("label") or item.get("field") or ""),
            "sample_count": int(shadow.get("sample_count") or 0),
            "minimum_sample_count": int(
                shadow.get("minimum_sample_count") or _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES
            ),
            "sample_gap": int(shadow.get("sample_gap") or 0),
            "latest_date": item.get("latest_date"),
        }
        for item in items
        if isinstance(shadow := item.get("shadow_evaluation"), dict)
        and shadow.get("status") == "history_short"
    ]
    suggested_refresh_products = _unique_texts(
        [
            _CRISIS_COMMODITY_FIELD_TO_PRODUCT.get(str(item.get("field") or ""))
            for item in shadow_short_items
        ]
    )
    return {
        "shadow_review_ready_count": statuses.count("shadow_review_ready"),
        "needs_current_data_count": statuses.count("needs_current_data"),
        "missing_data_count": statuses.count("missing_data"),
        "shadow_evaluation_ready_count": shadow_ready_count,
        "shadow_evaluation_short_count": shadow_short_count,
        "shadow_evaluation_status_counts": {
            status: shadow_statuses.count(status)
            for status in sorted(set(shadow_statuses))
            if status
        },
        "shadow_evaluation_short_items": shadow_short_items,
        "suggested_refresh_products": suggested_refresh_products,
        "shadow_evaluation_next_step": _crisis_commodity_shadow_next_step(
            ready_count=shadow_ready_count,
            short_count=shadow_short_count,
        ),
        "formula_change_required": True,
        "approval_required": True,
        "next_step": "商品旁证进入 Crisis Score 公式前，需要先完成历史回测、相关性检验、权重审批和版本记录。",
    }


def _crisis_commodity_shadow_next_step(*, ready_count: int, short_count: int) -> str:
    if ready_count > 0 and short_count == 0:
        return f"{ready_count} 个商品候选可进入人工复核；进入公式前仍需历史回测、相关性检验、权重审批和版本记录。"
    if ready_count > 0:
        return (
            f"{ready_count} 个商品候选可读，{short_count} 个样本不足；"
            "先补齐样本不足品种的历史数据，再做人工复核和权重审批。"
        )
    return "商品候选影子评估样本不足；先补齐历史数据，再做历史回测、相关性检验和权重审批。"


def _crisis_score_history(series_data: dict[str, list[tuple[date, float]]], report_date: date) -> pd.DataFrame:
    from backend.app.core_finance.macro.crisis_score import (  # noqa: PLC0415
        compute_crisis_indicators,
        compute_crisis_score,
    )

    indicators = compute_crisis_indicators(series_data)
    indicators = indicators[indicators.index.date <= report_date]
    if indicators.empty:
        return pd.DataFrame(columns=["crisis_score"])
    score_frame = compute_crisis_score(indicators)
    score_frame = score_frame[score_frame.index.date <= report_date]
    if score_frame.empty:
        return pd.DataFrame(columns=["crisis_score"])
    return score_frame[["crisis_score"]].dropna()


def _crisis_commodity_shadow_evaluation(frame: pd.DataFrame, crisis_history: pd.DataFrame) -> dict[str, object]:
    if frame.empty or crisis_history.empty or "crisis_score" not in crisis_history.columns:
        sample_count = 0
        return {
            "status": "history_short",
            "label": "影子评估样本不足",
            "sample_count": sample_count,
            "minimum_sample_count": _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
            "sample_gap": _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES - sample_count,
            "target": "crisis_score",
            "candidate_metric": "daily_return",
            "summary": "商品候选缺少足够历史样本，暂不能评估相关性。",
            "next_step": "先补齐商品期货历史数据，再做历史回测、相关性检验和权重审批。",
        }

    points = _frame_to_crisis_points(frame)
    if len(points) < 3:
        sample_count = len(points)
        return {
            "status": "history_short",
            "label": "影子评估样本不足",
            "sample_count": sample_count,
            "minimum_sample_count": _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
            "sample_gap": max(0, _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES - sample_count),
            "target": "crisis_score",
            "candidate_metric": "daily_return",
            "summary": f"商品候选仅 {sample_count} 个历史点，暂不能评估相关性。",
            "next_step": "先补齐商品期货历史数据，再做历史回测、相关性检验和权重审批。",
        }

    price_series = pd.Series({pd.Timestamp(point_date): value for point_date, value in points}, dtype="float64").sort_index()
    candidate_returns = price_series.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    aligned = pd.concat(
        {
            "candidate_return": candidate_returns,
            "crisis_score": crisis_history["crisis_score"],
        },
        axis=1,
    ).dropna()
    if len(aligned) < _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES:
        sample_count = int(len(aligned))
        return {
            "status": "history_short",
            "label": "影子评估样本不足",
            "sample_count": sample_count,
            "minimum_sample_count": _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
            "sample_gap": _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES - sample_count,
            "target": "crisis_score",
            "candidate_metric": "daily_return",
            "summary": f"商品候选与 Crisis Score 仅 {sample_count} 个重叠样本，暂不能评估相关性。",
            "next_step": "先补齐商品期货历史数据，再做历史回测、相关性检验和权重审批。",
        }

    same_day = _series_corr(aligned["candidate_return"], aligned["crisis_score"])
    lead_1d = _series_corr(aligned["candidate_return"].shift(1), aligned["crisis_score"])
    lag_1d = _series_corr(aligned["candidate_return"].shift(-1), aligned["crisis_score"])
    candidate_return_z = _latest_standard_score(aligned["candidate_return"])
    crisis_threshold = aligned["crisis_score"].quantile(0.75)
    crisis_rows = aligned[aligned["crisis_score"] >= crisis_threshold]
    hit_rate = None
    if not crisis_rows.empty:
        expected_sign = 1 if (same_day or 0) >= 0 else -1
        hit_rate = float((crisis_rows["candidate_return"] * expected_sign > 0).mean())

    return {
        "status": "review_ready",
        "label": "影子评估可读",
        "sample_count": int(len(aligned)),
        "window_start": aligned.index.min().date().isoformat(),
        "window_end": aligned.index.max().date().isoformat(),
        "target": "crisis_score",
        "candidate_metric": "daily_return",
        "same_day_correlation": same_day,
        "lead_1d_correlation": lead_1d,
        "lag_1d_correlation": lag_1d,
        "latest_return_z": candidate_return_z,
        "crisis_hit_rate": round(hit_rate, 2) if hit_rate is not None else None,
        "crisis_sample_count": int(len(crisis_rows)),
        "summary": (
            f"影子评估：样本 {len(aligned)}，同日相关 {_format_shadow_metric(same_day)}，"
            f"危机期命中率 {_format_shadow_metric(hit_rate)}。"
        ),
        "next_step": "进入公式前仍需历史回测、相关性检验、权重审批和版本记录。",
    }


def _series_corr(left: pd.Series, right: pd.Series) -> float | None:
    aligned = pd.concat({"left": left, "right": right}, axis=1).dropna()
    if len(aligned) < 3 or aligned["left"].nunique() < 2 or aligned["right"].nunique() < 2:
        return None
    value = aligned["left"].corr(aligned["right"])
    return round(float(value), 2) if pd.notna(value) else None


def _latest_standard_score(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES or clean.nunique() < 2:
        return None
    std = clean.std()
    if pd.isna(std) or float(std) == 0.0:
        return None
    value = (clean.iloc[-1] - clean.mean()) / std
    return round(float(value), 4) if pd.notna(value) else None


def _format_shadow_metric(value: float | None) -> str:
    return "缺失" if value is None else f"{value:.2f}"


def _crisis_commodity_shadow_impact(
    *,
    current_score: float | None,
    coverage: dict[str, object],
) -> dict[str, object]:
    items = [item for item in coverage.get("items", []) if isinstance(item, dict)]
    contributions = [
        contribution
        for item in items
        if (contribution := _crisis_commodity_shadow_contribution(item)) is not None
    ]
    delta = round(sum(float(item["contribution"]) for item in contributions), 4) if contributions else 0.0
    shadow_score = round(current_score + delta, 4) if current_score is not None else None
    return {
        "formula_version": _CRISIS_COMMODITY_SHADOW_FORMULA_VERSION,
        "scope": "commodity_shadow_v2_read_only",
        "current_score": round(current_score, 4) if current_score is not None else None,
        "shadow_score": shadow_score,
        "delta": delta,
        "direction": _crisis_commodity_shadow_direction(delta),
        "included_candidates": [str(item["field"]) for item in contributions],
        "candidate_count": len(contributions),
        "candidate_contributions": contributions,
        "weights": {
            "official_crisis_score": 1.0,
            "commodity_shadow": _CRISIS_COMMODITY_SHADOW_WEIGHT,
        },
        "warnings": ["SHADOW_SCORE_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"],
        "approval_required": True,
        "official_score_unchanged": True,
        "next_step": "先复核商品候选相关性和命中率，再确认 v2 权重；审批前不改变正式 Crisis Score。",
    }


def _crisis_commodity_shadow_contribution(item: dict[str, object]) -> dict[str, object] | None:
    shadow = item.get("shadow_evaluation")
    if not isinstance(shadow, dict) or shadow.get("status") != "review_ready":
        return None
    sample_count = int(shadow.get("sample_count") or 0)
    if sample_count < _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES:
        return None
    candidate_return_z = _float_or_none(shadow.get("latest_return_z"))
    if candidate_return_z is None:
        return None
    contribution = round(candidate_return_z * _CRISIS_COMMODITY_SHADOW_WEIGHT, 4)
    return {
        "field": str(item.get("field") or ""),
        "label": str(item.get("label") or item.get("field") or ""),
        "series_id": item.get("series_id"),
        "source": item.get("source"),
        "latest_date": item.get("latest_date"),
        "sample_count": sample_count,
        "candidate_metric": "daily_return_z",
        "candidate_value": round(candidate_return_z, 4),
        "weight": _CRISIS_COMMODITY_SHADOW_WEIGHT,
        "contribution": contribution,
        "used_in_official_score": False,
        "status": "shadow_only",
    }


def _crisis_commodity_shadow_direction(delta: float) -> str:
    if delta > 0.01:
        return "higher_stress"
    if delta < -0.01:
        return "lower_stress"
    return "unchanged"


def _crisis_commodity_candidate_admission(*, coverage: dict[str, object]) -> dict[str, object]:
    items = [item for item in coverage.get("items", []) if isinstance(item, dict)]
    admission_items = [_crisis_commodity_candidate_admission_item(item) for item in items]
    decision_counts = {
        "recommend_include": sum(1 for item in admission_items if item["decision"] == "recommend_include"),
        "watch": sum(1 for item in admission_items if item["decision"] == "watch"),
        "do_not_include": sum(1 for item in admission_items if item["decision"] == "do_not_include"),
    }
    return {
        "rule_version": _CRISIS_COMMODITY_ADMISSION_RULE_VERSION,
        "scope": "commodity_candidate_admission_read_only",
        "decision_counts": decision_counts,
        "items": admission_items,
        "warnings": ["CANDIDATE_ADMISSION_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"],
        "approval_required": True,
        "official_score_unchanged": True,
        "next_step": _crisis_commodity_admission_next_step(decision_counts),
    }


def _crisis_commodity_candidate_admission_item(item: dict[str, object]) -> dict[str, object]:
    shadow = item.get("shadow_evaluation")
    shadow = shadow if isinstance(shadow, dict) else {}
    sample_count = _int_or_none(shadow.get("sample_count"))
    minimum_sample_count = _int_or_none(shadow.get("minimum_sample_count")) or _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES
    crisis_sample_count = _int_or_none(shadow.get("crisis_sample_count"))
    crisis_hit_rate = _float_or_none(shadow.get("crisis_hit_rate"))
    max_abs_correlation = _crisis_commodity_max_abs_correlation(shadow)
    decision, reason, next_step = _crisis_commodity_admission_decision(
        shadow_status=str(shadow.get("status") or ""),
        sample_count=sample_count,
        minimum_sample_count=minimum_sample_count,
        crisis_sample_count=crisis_sample_count,
        crisis_hit_rate=crisis_hit_rate,
        max_abs_correlation=max_abs_correlation,
    )
    return {
        "field": str(item.get("field") or ""),
        "label": str(item.get("label") or item.get("field") or ""),
        "decision": decision,
        "decision_label": _crisis_commodity_admission_decision_label(decision),
        "reason": reason,
        "next_step": next_step,
        "sample_count": sample_count,
        "minimum_sample_count": minimum_sample_count,
        "crisis_sample_count": crisis_sample_count,
        "minimum_crisis_sample_count": _CRISIS_COMMODITY_ADMISSION_MIN_CRISIS_SAMPLES,
        "crisis_hit_rate": crisis_hit_rate,
        "max_abs_correlation": max_abs_correlation,
        "correlation_threshold": _CRISIS_COMMODITY_ADMISSION_MIN_CORRELATION,
        "latest_date": item.get("latest_date"),
        "series_id": item.get("series_id"),
        "source": item.get("source"),
        "used_in_official_score": False,
    }


def _crisis_commodity_admission_decision(
    *,
    shadow_status: str,
    sample_count: int | None,
    minimum_sample_count: int,
    crisis_sample_count: int | None,
    crisis_hit_rate: float | None,
    max_abs_correlation: float | None,
) -> tuple[str, str, str]:
    if (
        shadow_status != "review_ready"
        or sample_count is None
        or sample_count < minimum_sample_count
        or crisis_sample_count is None
        or crisis_sample_count < _CRISIS_COMMODITY_ADMISSION_MIN_CRISIS_SAMPLES
        or crisis_hit_rate is None
    ):
        return (
            "do_not_include",
            "样本不足，先补齐历史数据。",
            "先补齐历史样本和危机期样本，再重新生成准入评估。",
        )
    if max_abs_correlation is None or max_abs_correlation < _CRISIS_COMMODITY_ADMISSION_MIN_CORRELATION:
        return (
            "watch",
            "相关性偏弱，需人工复核。",
            "复核相关性与危机期命中率，并检查异常点后再决定是否提交审批。",
        )
    return (
        "recommend_include",
        "影子指标满足准入检查，仍需审批确认。",
        "提交人工复核、历史回测和 v2 权重审批。",
    )


def _crisis_commodity_admission_decision_label(decision: str) -> str:
    if decision == "recommend_include":
        return "建议纳入"
    if decision == "watch":
        return "继续观察"
    return "暂不纳入"


def _crisis_commodity_admission_next_step(decision_counts: dict[str, int]) -> str:
    recommend_count = decision_counts["recommend_include"]
    watch_count = decision_counts["watch"]
    reject_count = decision_counts["do_not_include"]
    if recommend_count == 0 and watch_count > 0 and reject_count == 0:
        return f"{watch_count} 个商品候选继续观察；先复核相关性、危机期命中率和异常点，再提交 v2 权重审批。"
    parts: list[str] = []
    if recommend_count:
        parts.append(f"{recommend_count} 个商品候选可提交人工复核和 v2 权重审批")
    if watch_count:
        parts.append(f"{watch_count} 个商品候选继续观察")
    if reject_count:
        parts.append(f"{reject_count} 个商品候选先补齐历史样本")
    if not parts:
        return "暂无可用商品候选；先补齐商品期货历史数据。"
    return "；".join(parts) + "；审批前不改变正式 Crisis Score。"


def _crisis_commodity_max_abs_correlation(shadow: dict[str, object]) -> float | None:
    values = [
        abs(value)
        for key in ("same_day_correlation", "lead_1d_correlation", "lag_1d_correlation")
        if (value := _float_or_none(shadow.get(key))) is not None
    ]
    return round(max(values), 4) if values else None


def _crisis_commodity_candidate_approval_pack(
    *,
    admission: dict[str, object],
    shadow_impact: dict[str, object],
) -> dict[str, object]:
    items = [item for item in admission.get("items", []) if isinstance(item, dict)]
    decision_counts = admission.get("decision_counts") if isinstance(admission.get("decision_counts"), dict) else {}
    recommended_fields = [str(item.get("field") or "") for item in items if item.get("decision") == "recommend_include"]
    watch_fields = [str(item.get("field") or "") for item in items if item.get("decision") == "watch"]
    rejected_fields = [str(item.get("field") or "") for item in items if item.get("decision") == "do_not_include"]
    summary = (
        f"审批材料：建议纳入 {int(decision_counts.get('recommend_include') or 0)}，"
        f"继续观察 {int(decision_counts.get('watch') or 0)}，"
        f"暂不纳入 {int(decision_counts.get('do_not_include') or 0)}；"
        "审批前不改变正式 Crisis Score。"
    )
    copy_text = _crisis_commodity_approval_copy_text(
        summary=summary,
        admission=admission,
        shadow_impact=shadow_impact,
        items=items,
    )
    return {
        "pack_version": _CRISIS_COMMODITY_APPROVAL_PACK_VERSION,
        "scope": "commodity_candidate_approval_read_only",
        "source_rule_version": admission.get("rule_version"),
        "shadow_formula_version": shadow_impact.get("formula_version"),
        "decision_counts": {
            "recommend_include": int(decision_counts.get("recommend_include") or 0),
            "watch": int(decision_counts.get("watch") or 0),
            "do_not_include": int(decision_counts.get("do_not_include") or 0),
        },
        "recommended_fields": recommended_fields,
        "watch_fields": watch_fields,
        "rejected_fields": rejected_fields,
        "summary": summary,
        "copy_text": copy_text,
        "warnings": ["APPROVAL_PACK_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"],
        "approval_required": True,
        "official_score_unchanged": True,
    }


def _crisis_commodity_approval_copy_text(
    *,
    summary: str,
    admission: dict[str, object],
    shadow_impact: dict[str, object],
    items: list[dict[str, object]],
) -> str:
    lines = [
        "Crisis Score 商品候选审批材料",
        summary,
        f"规则版本 {admission.get('rule_version')}",
        f"影子公式 {shadow_impact.get('formula_version')}",
        f"正式 Crisis Score {_format_approval_number(shadow_impact.get('current_score'))}",
        f"shadow score {_format_approval_number(shadow_impact.get('shadow_score'))}",
        f"shadow delta {_format_approval_signed_number(shadow_impact.get('delta'))}",
        "边界：审批前不改变正式 Crisis Score，不改变正式权重，不写入数据库。",
        "候选明细：",
    ]
    lines.extend(_crisis_commodity_approval_item_line(item) for item in items)
    return "\n".join(lines)


def _crisis_commodity_approval_item_line(item: dict[str, object]) -> str:
    return (
        f"{item.get('label') or item.get('field')} · {item.get('decision_label')} · {item.get('reason')} · "
        f"样本 {_format_approval_count(item.get('sample_count'))}/{_format_approval_count(item.get('minimum_sample_count'))} · "
        f"危机样本 {_format_approval_count(item.get('crisis_sample_count'))}/"
        f"{_format_approval_count(item.get('minimum_crisis_sample_count'))} · "
        f"命中率 {_format_approval_percent(item.get('crisis_hit_rate'))} · "
        f"最大相关 {_format_approval_number(item.get('max_abs_correlation'))}/"
        f"{_format_approval_number(item.get('correlation_threshold'))} · "
        f"source {item.get('source') or '缺失'} · series {item.get('series_id') or '缺失'} · "
        "审批前不改变正式 Crisis Score"
    )


def _format_approval_count(value: object) -> str:
    number = _int_or_none(value)
    return str(number) if number is not None else "缺失"


def _format_approval_percent(value: object) -> str:
    number = _float_or_none(value)
    return f"{number * 100:.1f}%" if number is not None else "缺失"


def _format_approval_number(value: object) -> str:
    number = _float_or_none(value)
    return f"{number:.2f}" if number is not None else "缺失"


def _format_approval_signed_number(value: object) -> str:
    number = _float_or_none(value)
    if number is None:
        return "缺失"
    return f"{number:+.2f}"


def _crisis_commodity_candidate_decision(*, available: bool, date_alignment_status: str) -> dict[str, object]:
    if not available:
        return {
            "status": "missing_data",
            "label": "缺少数据",
            "reason": "商品旁证未命中，不能进入影子评估。",
            "next_step": "先完成商品期货刷新或源映射修复。",
        }
    if date_alignment_status != "aligned":
        return {
            "status": "needs_current_data",
            "label": "需要补齐当日数据",
            "reason": "商品旁证已命中但与分析日不一致；当前仍作为 supplemental_observation。",
            "next_step": "补齐到分析日后，再进入历史回测、相关性检验和权重审批。",
        }
    return {
        "status": "shadow_review_ready",
        "label": "影子评估就绪",
        "reason": "数据已命中且与分析日同日；当前仍作为 supplemental_observation，不改变 Crisis Score 公式。",
        "next_step": "完成历史回测、相关性检验、权重审批后，才能作为公式候选提交。",
    }


def _latest_crisis_input_date(duckdb_path: str | Path) -> date | None:
    latest_dates: list[date] = []
    for config in _CRISIS_SCORE_INPUTS:
        check = _source_check(str(config["alias"]), duckdb_path)
        latest = check.get("latest")
        if isinstance(latest, dict):
            latest_date = _coerce_frame_date(latest.get("date"))
            if latest_date is not None:
                latest_dates.append(latest_date)
    return max(latest_dates) if latest_dates else None


def _crisis_score_card_without_analysis_date(
    definition: dict[str, object],
    duckdb_path: str | Path,
    report_date: date | None,
) -> dict[str, object]:
    if report_date is None:
        return _unavailable_capability_result(definition, "缺少可用分析日期")
    raw_result = _run_capability(
        "crisis_score_cn",
        lambda: _compute_crisis_score_capability(duckdb_path, report_date),
    )
    warnings = [str(item) for item in raw_result.get("warnings", []) if item]
    reason = "缺少全局分析日期，Crisis Score 使用自身输入最新日期补充证据"
    if reason not in warnings:
        warnings.insert(0, reason)
    enriched = dict(raw_result)
    if str(enriched.get("data_status") or "").lower() == "complete":
        enriched["data_status"] = "degraded"
    enriched["warnings"] = warnings
    return _capability_result_card(definition, enriched)


def _frame_to_crisis_points(frame: pd.DataFrame) -> list[tuple[date, float]]:
    points: list[tuple[date, float]] = []
    if frame.empty:
        return points
    for _, row in frame.sort_values("date").iterrows():
        sample_date = _coerce_frame_date(row.get("date"))
        value = _float_or_none(row.get("value"))
        if sample_date is None or value is None:
            continue
        points.append((sample_date, value))
    return points


def _run_capability(
    key: str,
    compute: Callable[[], dict[str, object]],
) -> dict[str, object]:
    try:
        return compute()
    except Exception as exc:  # pragma: no cover - surfaced as degraded UI evidence
        return {
            "data_status": "unavailable",
            "headline": f"{key} 计算失败",
            "warnings": [f"{type(exc).__name__}: {exc}"],
        }


def _with_capability_input_evidence(
    key: str,
    result: dict[str, object],
    *,
    duckdb_path: str | Path,
    report_date: date,
    wide_rows: list[dict[str, object]],
    source_check_cache: dict[str, dict[str, object]] | None = None,
    source_frames_by_alias: dict[str, pd.DataFrame] | None = None,
) -> dict[str, object]:
    requirements = _CAPABILITY_INPUT_REQUIREMENTS.get(key)
    if not requirements:
        return result

    resolved_source_check_cache = source_check_cache if source_check_cache is not None else {}
    _source_checks_for_aliases(
        (
            str(alias)
            for requirement in requirements
            for alias in requirement.get("aliases", ())
        ),
        duckdb_path,
        source_check_cache=resolved_source_check_cache,
        end=report_date.isoformat(),
        frames_by_alias=source_frames_by_alias,
    )
    inputs = [
        _capability_input_evidence_item(
            requirement,
            duckdb_path=duckdb_path,
            report_date=report_date,
            wide_rows=wide_rows,
            source_check_cache=resolved_source_check_cache,
        )
        for requirement in requirements
    ]
    missing_inputs = [
        str(item["warning"])
        for item in inputs
        if item["required"] and not item["available"]
    ]
    warnings = [str(item) for item in result.get("warnings", []) if item]
    for warning in missing_inputs:
        if warning not in warnings:
            warnings.append(warning)

    enriched = dict(result)
    if missing_inputs and str(enriched.get("data_status") or "").lower() == "complete":
        enriched["data_status"] = "degraded"
    enriched["warnings"] = warnings
    enriched["input_evidence"] = {
        "inputs": inputs,
        "missing_inputs": missing_inputs,
        "sources": _unique_sorted_texts(item.get("source") for item in inputs),
        "latest_dates": _unique_sorted_texts(item.get("latest_date") for item in inputs),
    }
    return enriched


def _capability_input_evidence_item(
    requirement: dict[str, object],
    *,
    duckdb_path: str | Path,
    report_date: date,
    wide_rows: list[dict[str, object]],
    source_check_cache: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in requirement.get("aliases", ()))
    check = _first_available_source_check(
        aliases,
        duckdb_path,
        report_date,
        source_check_cache=source_check_cache,
    )
    latest = check.get("latest") if isinstance(check.get("latest"), dict) else None
    field = str(requirement["field"])
    derived = bool(requirement.get("derived", False))
    value = _latest_wide_field_value(field, wide_rows) if derived else None
    if value is None and isinstance(latest, dict):
        value = latest.get("value")
    available = value is not None if derived else latest is not None
    return {
        "field": field,
        "label": str(requirement["label"]),
        "aliases": list(aliases),
        "warning": str(requirement["warning"]),
        "required": bool(requirement.get("required", True)),
        "available": available,
        "row_count": int(check.get("row_count") or 0),
        "latest_date": latest.get("date") if isinstance(latest, dict) else None,
        "series_id": latest.get("series_id") if isinstance(latest, dict) else None,
        "source": latest.get("vendor_name") if isinstance(latest, dict) else None,
        "value": value,
    }


def _first_available_source_check(
    aliases: tuple[str, ...],
    duckdb_path: str | Path,
    report_date: date,
    *,
    source_check_cache: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    checks = [
        source_check_cache[alias]
        if source_check_cache is not None and alias in source_check_cache
        else _source_check(alias, duckdb_path, end=report_date.isoformat())
        for alias in aliases
    ]
    for check in checks:
        if check["latest"]:
            return check
    return checks[0] if checks else {"alias": "", "row_count": 0, "latest": None}


def _latest_wide_field_value(field: str, wide_rows: list[dict[str, object]]) -> float | None:
    for row in wide_rows:
        value = _float_or_none(row.get(field))
        if value is not None:
            return value
    return None


def _unique_sorted_texts(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return sorted(out)


def _parse_report_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _load_macro_curve_rows(duckdb_path: str | Path, report_date: date) -> list[dict[str, object]]:
    return macro_toolkit_service.load_macro_curve_rows(duckdb_path, report_date)


def _load_macro_wide_rows(
    duckdb_path: str | Path,
    report_date: date,
    curve_rows: list[dict[str, object]],
    *,
    frames_by_alias: dict[str, pd.DataFrame] | None = None,
) -> list[dict[str, object]]:
    wide_by_date: dict[date, dict[str, float]] = {report_date: {}}
    fields = [field for field, _ in _WIDE_SERIES_ALIASES]
    resolved_frames_by_alias = frames_by_alias or {}
    missing_aliases = tuple(
        dict.fromkeys(alias for _, alias in _WIDE_SERIES_ALIASES if alias not in resolved_frames_by_alias)
    )
    if missing_aliases:
        resolved_frames_by_alias = {
            **resolved_frames_by_alias,
            **load_series_by_aliases(
                missing_aliases,
                end=report_date.isoformat(),
                duckdb_path=duckdb_path,
            ),
        }
    for field, alias in _WIDE_SERIES_ALIASES:
        frame = resolved_frames_by_alias[alias]
        if frame.empty:
            continue
        for _, sample in frame.iterrows():
            sample_date = _coerce_frame_date(sample.get("date"))
            value = _float_or_none(sample.get("value"))
            if sample_date is None or sample_date > report_date or value is None:
                continue
            wide_by_date.setdefault(sample_date, {})[field] = value

    for row in curve_rows:
        row_date = _parse_report_date(str(row.get("biz_date") or ""))
        if row_date is not None and row_date <= report_date:
            wide_by_date.setdefault(row_date, {})

    last_seen: dict[str, float] = {}
    for sample_date in sorted(wide_by_date):
        current = wide_by_date[sample_date]
        for field in fields:
            if field not in current and field in last_seen:
                current[field] = last_seen[field]
        for field in fields:
            value = current.get(field)
            if value is not None:
                last_seen[field] = value

    curves_by_date = build_curve_history(curve_rows, report_date=report_date)
    enrich_wide_with_curve_market_fields(wide_by_date, curves_by_date)
    return sort_wide_rows_for_macro(wide_by_date, report_date=report_date)


def _load_latest_risk_tensor_row(
    duckdb_path: str | Path,
    report_date: date,
) -> dict[str, object] | None:
    return macro_toolkit_service.load_latest_risk_tensor_row(duckdb_path, report_date)


def _risk_tensor_to_liquidity_inputs(
    row: dict[str, object] | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], float | None]:
    if row is None:
        return [], [], None

    total_assets = _float_or_none(row.get("total_market_value"))
    proxy_rows: list[dict[str, object]] = []
    top_share = _float_or_none(row.get("issuer_top5_weight"))
    dv01 = _float_or_none(row.get("portfolio_dv01"))
    bond_count = _float_or_none(row.get("bond_count"))
    if top_share is not None or dv01 is not None:
        proxy_rows.append(
            {
                "book_id": "portfolio",
                "share_of_abs_dv01": top_share,
                "dv01_sum": dv01,
                "row_count": int(bond_count or 0),
            }
        )

    bucket_rows: list[dict[str, object]] = []
    asset_30 = _float_or_none(row.get("asset_cashflow_30d"))
    asset_90 = _float_or_none(row.get("asset_cashflow_90d"))
    liability_30 = _float_or_none(row.get("liability_cashflow_30d"))
    liability_90 = _float_or_none(row.get("liability_cashflow_90d"))
    gap_30 = _float_or_none(row.get("liquidity_gap_30d"))
    gap_90 = _float_or_none(row.get("liquidity_gap_90d"))
    gap_ratio_30 = _float_or_none(row.get("liquidity_gap_30d_ratio"))

    if any(value is not None for value in (asset_30, liability_30, gap_30)):
        net_30 = gap_30 if gap_30 is not None else (asset_30 or 0.0) - (liability_30 or 0.0)
        bucket_rows.append(
            {
                "bucket_name": "<=1M",
                "asset_amount": asset_30 or 0.0,
                "liability_amount": liability_30 or 0.0,
                "net_gap": net_30,
                "cumulative_gap": gap_30 if gap_30 is not None else net_30,
                "gap_ratio": gap_ratio_30,
                "asset_row_count": 1 if asset_30 is not None else 0,
                "liability_row_count": 1 if liability_30 is not None else 0,
            }
        )

    if any(value is not None for value in (asset_90, liability_90, gap_90)):
        net_90 = (gap_90 or 0.0) - (gap_30 or 0.0) if gap_90 is not None else (asset_90 or 0.0) - (asset_30 or 0.0) - ((liability_90 or 0.0) - (liability_30 or 0.0))
        bucket_rows.append(
            {
                "bucket_name": "1-3M",
                "asset_amount": max(0.0, (asset_90 or 0.0) - (asset_30 or 0.0)),
                "liability_amount": max(0.0, (liability_90 or 0.0) - (liability_30 or 0.0)),
                "net_gap": net_90,
                "cumulative_gap": gap_90 if gap_90 is not None else net_90,
                "gap_ratio": (net_90 / total_assets) if total_assets else None,
                "asset_row_count": 1 if asset_90 is not None else 0,
                "liability_row_count": 1 if liability_90 is not None else 0,
            }
        )
    return proxy_rows, bucket_rows, total_assets


def _load_latest_bond_positions(
    duckdb_path: str | Path,
    report_date: date,
) -> list[dict[str, object]]:
    return macro_toolkit_service.load_latest_bond_positions(duckdb_path, report_date)


def _current_gov_curve(
    curve_rows: list[dict[str, object]],
    report_date: date,
) -> dict[str, float]:
    curves_by_date = build_curve_history(curve_rows, report_date=report_date)
    for sample_date in sorted(curves_by_date.keys(), reverse=True):
        government_curve = curves_by_date.get(sample_date, {}).get("CN_GOVT", {})
        if government_curve:
            return {tenor: float(rate) for tenor, rate in government_curve.items()}
    return {}


def _capability_result_card(
    definition: dict[str, object],
    result: dict[str, object] | None,
) -> dict[str, object]:
    raw_result = result or {}
    status = _capability_result_status(str(definition["key"]), raw_result)
    tone = _capability_result_tone(str(definition["key"]), raw_result, status)
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "status": status,
        "tone": tone,
        "score": _capability_result_score(str(definition["key"]), raw_result),
        "headline": _capability_result_headline(str(definition["key"]), raw_result),
        "primary_metric": _capability_primary_metric(str(definition["key"]), raw_result),
        "input_evidence": raw_result.get("input_evidence"),
        "evidence": _capability_result_evidence(str(definition["key"]), raw_result),
        "warnings": [str(item) for item in raw_result.get("warnings", []) if item],
        "result": raw_result,
    }


def _unavailable_capability_result(
    definition: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "status": "unavailable",
        "tone": "missing",
        "score": None,
        "headline": reason,
        "primary_metric": None,
        "evidence": [],
        "warnings": [reason],
        "result": {"data_status": "unavailable", "warnings": [reason]},
    }


def _capability_result_status(key: str, result: dict[str, object]) -> str:
    data_status = str(result.get("data_status") or "").lower()
    if data_status in {"complete", "degraded", "unavailable"}:
        return data_status
    if key == "yield_curve_shape" and result.get("shape") == "Unavailable":
        return "unavailable"
    if key == "credit_spread_risk" and result.get("risk_level") == "UNAVAILABLE":
        return "unavailable"
    warnings = result.get("warnings")
    if isinstance(warnings, list) and warnings:
        return "degraded"
    return "complete" if result else "unavailable"


def _capability_result_tone(key: str, result: dict[str, object], status: str) -> str:
    if status == "unavailable":
        return "missing"
    if key == "monetary_policy_stance":
        stance = str(result.get("stance_label") or "")
        if stance == "accommodative":
            return "positive"
        if stance == "tight":
            return "negative"
    if key == "credit_spread_risk":
        risk = str(result.get("risk_level") or "")
        if risk in {"HIGH", "CRITICAL"}:
            return "negative"
        if risk == "LOW":
            return "positive"
    if key == "liquidity_stress":
        stress = str(result.get("stress_level") or "")
        if stress in {"HIGH", "CRITICAL"}:
            return "negative"
        if stress == "LOW":
            return "positive"
    if key == "crisis_score_cn":
        score = _float_or_none(result.get("crisis_score"))
        if score is None:
            return "missing"
        if score >= 1:
            return "negative"
        if score < 0:
            return "positive"
        return "neutral"
    if key == "cross_market_linkage":
        risk = str(result.get("overall_risk") or "")
        if risk == "HIGH":
            return "negative"
        if risk == "LOW":
            return "positive"
    if key == "economic_cycle":
        phase = str(result.get("cycle_phase") or "")
        if phase == "recovery":
            return "positive"
        if phase in {"stagflation", "recession"}:
            return "negative"
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        pnl_pct = _float_or_none(worst.get("pnl_pct")) if worst else None
        if pnl_pct is not None and pnl_pct <= -0.5:
            return "negative"
        if pnl_pct is not None and pnl_pct >= 0:
            return "positive"
    return "neutral"


def _capability_result_score(key: str, result: dict[str, object]) -> float | None:
    score_fields = {
        "monetary_policy_stance": "stance_score",
        "credit_spread_risk": "risk_score",
        "crisis_score_cn": "crisis_score",
        "leading_indicator": "lei_index",
        "liquidity_stress": "stress_score",
        "rate_turning_point": "percentile_1y",
        "economic_cycle": "growth_score",
    }
    if key in score_fields:
        return _round_float(_float_or_none(result.get(score_fields[key])))
    if key == "yield_curve_shape":
        spreads = result.get("spreads") if isinstance(result.get("spreads"), dict) else {}
        return _round_float(_float_or_none(spreads.get("10Y-1Y") if isinstance(spreads, dict) else None))
    if key == "cross_market_linkage":
        risk_score = {"LOW": 25.0, "MEDIUM": 55.0, "HIGH": 85.0}.get(str(result.get("overall_risk")), None)
        return risk_score
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        return _round_float(_float_or_none(worst.get("pnl_pct")) if worst else None)
    return None


def _capability_result_headline(key: str, result: dict[str, object]) -> str:
    for field in ("headline", "interpretation", "recommendation"):
        value = result.get(field)
        if value:
            return str(value)
    if key == "leading_indicator":
        return f"LEI {result.get('lei_index', 'n/a')} · {result.get('economic_state', 'unknown')} · {result.get('trend', 'flat')}"
    if key == "economic_cycle":
        return f"周期位置：{result.get('cycle_phase_cn', 'unknown')}"
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        if worst:
            return f"压力最大情景：{worst.get('name_cn') or worst.get('name')}，PnL {worst.get('pnl_pct')}%"
    return "暂无可解释结果"


def _capability_primary_metric(
    key: str,
    result: dict[str, object],
) -> dict[str, object] | None:
    if key == "monetary_policy_stance":
        return _metric("立场得分", result.get("stance_score"), "")
    if key == "yield_curve_shape":
        spreads = result.get("spreads") if isinstance(result.get("spreads"), dict) else {}
        return _metric("10Y-1Y", spreads.get("10Y-1Y") if isinstance(spreads, dict) else None, "bp")
    if key == "credit_spread_risk":
        return _metric("AAA利差", result.get("aaa_spread_bp"), "bp")
    if key == "leading_indicator":
        return _metric("LEI", result.get("lei_index"), "")
    if key == "liquidity_stress":
        return _metric("压力分", result.get("stress_score"), "")
    if key == "crisis_score_cn":
        return _metric("Crisis Score", result.get("crisis_score"), "")
    if key == "cross_market_linkage":
        return _metric("联动风险", result.get("overall_risk"), "")
    if key == "rate_turning_point":
        return _metric("10Y国债", result.get("current_10y"), "%")
    if key == "economic_cycle":
        return _metric("周期", result.get("cycle_phase_cn"), "")
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        return _metric("最差PnL", worst.get("pnl_pct") if worst else None, "%")
    return None


def _capability_result_evidence(key: str, result: dict[str, object]) -> list[str]:
    if not result:
        return []
    if key == "monetary_policy_stance":
        metrics = result.get("key_metrics") if isinstance(result.get("key_metrics"), dict) else {}
        return _compact_evidence(
            [
                _format_evidence("DR007", metrics.get("dr007"), "%") if isinstance(metrics, dict) else None,
                _format_evidence("10Y-1Y", metrics.get("gov_slope_10y_1y_bp"), "bp") if isinstance(metrics, dict) else None,
                _format_evidence("AAA spread", metrics.get("aaa_spread_bp"), "bp") if isinstance(metrics, dict) else None,
            ]
        )
    if key == "yield_curve_shape":
        spreads = result.get("spreads") if isinstance(result.get("spreads"), dict) else {}
        return _compact_evidence(
            [
                f"shape={result.get('shape')}",
                _format_evidence("10Y-1Y", spreads.get("10Y-1Y") if isinstance(spreads, dict) else None, "bp"),
                _format_evidence("percentile", result.get("percentile_1y"), "%"),
            ]
        )
    if key == "credit_spread_risk":
        return _compact_evidence(
            [
                f"risk={result.get('risk_level')}",
                _format_evidence("AAA", result.get("aaa_spread_bp"), "bp"),
                _format_evidence("AA-AAA", result.get("aa_minus_aaa_bp"), "bp"),
            ]
        )
    if key == "leading_indicator":
        return _compact_evidence(
            [
                _format_evidence("LEI", result.get("lei_index"), ""),
                f"state={result.get('economic_state')}",
                f"trend={result.get('trend')}",
            ]
        )
    if key == "liquidity_stress":
        return _compact_evidence(
            [
                _format_evidence("stress", result.get("stress_score"), ""),
                _format_evidence("short_gap_ratio", result.get("short_term_gap_ratio"), ""),
                _format_evidence("negative_buckets", result.get("negative_bucket_count"), ""),
            ]
        )
    if key == "crisis_score_cn":
        return _compact_evidence(
            [
                _format_evidence("score", result.get("crisis_score"), ""),
                f"regime={result.get('regime')}",
                _format_evidence("percentile", result.get("percentile"), "%"),
            ]
        )
    if key == "cross_market_linkage":
        return _compact_evidence(
            [
                f"risk={result.get('overall_risk')}",
                _format_evidence("bond_fx_corr", result.get("bond_fx_corr"), ""),
                _format_evidence("bond_oil_corr", result.get("bond_commodity_corr"), ""),
            ]
        )
    if key == "rate_turning_point":
        return _compact_evidence(
            [
                f"direction={result.get('direction')}",
                _format_evidence("10Y", result.get("current_10y"), "%"),
                _format_evidence("5d", result.get("change_5d_bp"), "bp"),
            ]
        )
    if key == "economic_cycle":
        return _compact_evidence(
            [
                f"phase={result.get('cycle_phase_cn')}",
                _format_evidence("growth", result.get("growth_score"), ""),
                _format_evidence("inflation", result.get("inflation_score"), ""),
            ]
        )
    if key == "macro_portfolio_impact":
        portfolio = result.get("portfolio") if isinstance(result.get("portfolio"), dict) else {}
        worst = _worst_portfolio_scenario(result)
        return _compact_evidence(
            [
                _format_evidence("total_mv", portfolio.get("total_mv") if isinstance(portfolio, dict) else None, ""),
                _format_evidence("duration", portfolio.get("weighted_duration") if isinstance(portfolio, dict) else None, ""),
                _format_evidence("worst_pnl", worst.get("pnl_pct") if worst else None, "%"),
            ]
        )
    return []


def _decision_summary_card(
    definition: dict[str, object],
    cards: list[dict[str, object]],
    report_date: date,
) -> dict[str, object]:
    usable_cards = [card for card in cards if card["status"] in {"complete", "degraded"}]
    positive_count = sum(1 for card in usable_cards if card["tone"] == "positive")
    negative_count = sum(1 for card in usable_cards if card["tone"] == "negative")
    missing_count = sum(1 for card in cards if card["status"] == "unavailable")
    if negative_count > positive_count:
        tone = "negative"
        headline = "宏观信号偏谨慎，优先控制久期和信用敞口。"
    elif positive_count > negative_count:
        tone = "positive"
        headline = "宏观信号偏支持，组合可保留适度久期与高等级信用。"
    else:
        tone = "neutral"
        headline = "宏观信号分化，维持中性观察。"
    status = "complete" if len(usable_cards) >= 7 and missing_count == 0 else "degraded"
    score = round(50 + (positive_count - negative_count) * 8 - missing_count * 3, 2)
    evidence = [
        f"{card['legacy_module']} {card['headline']}"
        for card in usable_cards[:4]
        if card.get("headline")
    ]
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "status": status,
        "tone": tone,
        "score": max(0.0, min(100.0, score)),
        "headline": headline,
        "primary_metric": _metric("可用模块", len(usable_cards), "/9"),
        "evidence": evidence,
        "warnings": ["部分模块数据降级或不可用"] if status == "degraded" else [],
        "result": {
            "report_date": report_date.isoformat(),
            "data_status": status,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "missing_count": missing_count,
            "usable_count": len(usable_cards),
            "headline": headline,
        },
    }


def _metric(label: str, value: object, unit: str) -> dict[str, object] | None:
    if value is None:
        return None
    rounded = _round_float(_float_or_none(value))
    return {
        "label": label,
        "value": rounded if rounded is not None else value,
        "unit": unit,
    }


def _worst_portfolio_scenario(result: dict[str, object]) -> dict[str, object] | None:
    scenarios = result.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return None
    scenario_dicts = [item for item in scenarios if isinstance(item, dict)]
    if not scenario_dicts:
        return None
    return min(scenario_dicts, key=lambda item: _float_or_none(item.get("pnl_pct")) or 0.0)


def _compact_evidence(items: list[str | None]) -> list[str]:
    return [item for item in items if item and "None" not in item and "nan" not in item.lower()]


def _format_evidence(label: str, value: object, unit: str) -> str | None:
    if value is None:
        return None
    rounded = _round_float(_float_or_none(value))
    display = rounded if rounded is not None else value
    return f"{label}={display}{unit}"


def _round_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _int_or_none(value: object) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None


def _coerce_frame_date(value: object) -> date | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except (AttributeError, TypeError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _analysis_indicators(duckdb_path: str | Path) -> list[dict[str, object]]:
    frames_by_alias = load_series_by_aliases(
        tuple(str(config["alias"]) for config in _ANALYSIS_INDICATORS),
        duckdb_path=duckdb_path,
    )
    indicators: list[dict[str, object]] = []
    for config in _ANALYSIS_INDICATORS:
        frame = frames_by_alias[str(config["alias"])]
        indicators.append(_indicator_payload(config, frame))
    return indicators


def _indicator_payload(config: dict[str, str], frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {
            "key": config["key"],
            "alias": config["alias"],
            "label": config["label"],
            "group": config["group"],
            "unit": config["unit"],
            "row_count": 0,
            "latest_date": None,
            "latest_value": None,
            "previous_value": None,
            "change": None,
            "change_pct": None,
            "source": None,
            "series_id": None,
            "quality": "missing",
        }

    ordered = frame.sort_values("date")
    latest = ordered.iloc[-1]
    previous = ordered.iloc[-2] if len(ordered) > 1 else None
    latest_value = float(latest["value"])
    previous_value = float(previous["value"]) if previous is not None else None
    change = latest_value - previous_value if previous_value is not None else None
    change_pct = (
        round((change / abs(previous_value)) * 100, 4)
        if change is not None and previous_value not in (None, 0)
        else None
    )
    return {
        "key": config["key"],
        "alias": config["alias"],
        "label": config["label"],
        "group": config["group"],
        "unit": config["unit"],
        "row_count": int(len(ordered)),
        "latest_date": str(latest["date"])[:10],
        "latest_value": round(latest_value, 4),
        "previous_value": round(previous_value, 4) if previous_value is not None else None,
        "change": round(change, 4) if change is not None else None,
        "change_pct": change_pct,
        "source": str(latest["vendor_name"]),
        "series_id": str(latest["series_id"]),
        "quality": "ok",
    }


def _analysis_signal_cards(
    indicator_by_key: dict[str, dict[str, object]],
    output_files: list[dict[str, object]],
    capability_results: list[dict[str, object]],
    a_share_risk: dict[str, object] | None = None,
    *,
    capabilities_deferred: bool = False,
) -> list[dict[str, object]]:
    cards = [
        _crisis_score_card(capability_results, deferred=capabilities_deferred),
        _a_share_stampede_risk_card(a_share_risk),
        _liquidity_card(indicator_by_key),
        _risk_appetite_card(indicator_by_key),
        _credit_card(indicator_by_key),
        _script_output_card(output_files),
    ]
    return cards


_HASON_REQUIRED_OUTPUTS = ("final_signal.csv", "crowding_latest.csv")
_HASON_BUSINESS_TZ = timezone(timedelta(hours=8))
_HASON_OUTPUT_DATE_COLUMNS = ("日期", "date", "trade_date", "as_of_date")
_HASON_MODULES: tuple[dict[str, object], ...] = (
    {
        "key": "market_state",
        "label": "Market state",
        "status": "integrated",
        "scripts": ("merrill_clock_cn", "regime_switch_cn", "dcc_garch_cn", "garch_multi_asset"),
        "evidence": ("cycle", "volatility", "correlation"),
    },
    {
        "key": "allocation",
        "label": "Allocation",
        "status": "integrated",
        "scripts": ("risk_parity_cn", "rebalance_cn"),
        "evidence": ("risk parity", "risk budget", "rebalancing"),
    },
    {
        "key": "strategy_selection",
        "label": "Strategy selection",
        "status": "integrated",
        "scripts": ("cta_trend_cn", "signal_aggregator", "crowding_cn"),
        "evidence": ("CTA trend", "crowding filter", "final signal"),
    },
    {
        "key": "risk_management",
        "label": "Risk management",
        "status": "integrated",
        "scripts": ("crisis_score_cn", "risk_monitor", "dcc_garch_cn"),
        "evidence": ("Crisis Score", "vol-correlation crisis", "de-risking"),
    },
    {
        "key": "performance_review",
        "label": "Performance review",
        "status": "integrated",
        "scripts": ("performance_metrics_cn", "backtest_cn"),
        "evidence": ("Sharpe", "Sortino", "Calmar"),
    },
)


def _hason_macro_strategy_summary(
    output_files: list[dict[str, object]],
    *,
    analysis_date: str | None = None,
) -> dict[str, object]:
    scripts_by_name = {script.name: script for script in iter_toolkit_scripts()}
    runtime_outputs = _hason_runtime_outputs(output_files, analysis_date=analysis_date)
    missing_outputs = [
        str(item["name"])
        for item in runtime_outputs
        if item["freshness_status"] == "missing"
    ]
    stale_outputs = [
        str(item["name"])
        for item in runtime_outputs
        if item["freshness_status"] == "stale"
    ]
    runtime_output_gaps = [
        str(item["name"])
        for item in runtime_outputs
        if item["freshness_status"] != "current"
    ]
    runtime_output_status = _hason_runtime_output_status(runtime_outputs)
    modules = [_hason_module_payload(module, scripts_by_name) for module in _HASON_MODULES]
    ready_modules = sum(1 for module in modules if module["status"] == "integrated")
    partial_modules = sum(1 for module in modules if module["status"] == "partial")
    missing_modules = sum(1 for module in modules if module["status"] == "missing")
    missing_script_count = len(
        {
            str(script_name)
            for module in modules
            for script_name in module["missing_scripts"]
        }
    )
    readiness_ratio = round(ready_modules / len(modules), 4) if modules else 0
    status = (
        "observation_ready"
        if runtime_output_status == "current" and ready_modules == len(modules)
        else "degraded"
    )
    return {
        "key": "hason_macro_strategy",
        "framework_name": "Hason macro hedge due-diligence framework",
        "basis": "analytical",
        "observation_only": True,
        "formal_use_allowed": False,
        "formal_metric_id": None,
        "status": status,
        "display_status": "visible",
        "readiness": {
            "ready_modules": ready_modules,
            "partial_modules": partial_modules,
            "missing_modules": missing_modules,
            "missing_script_count": missing_script_count,
            "total_modules": len(modules),
            "ratio": readiness_ratio,
        },
        "modules": modules,
        "runtime_output_status": runtime_output_status,
        "runtime_outputs": runtime_outputs,
        "required_runtime_outputs": list(_HASON_REQUIRED_OUTPUTS),
        "runtime_output_gaps": runtime_output_gaps,
        "missing_runtime_outputs": missing_outputs,
        "stale_runtime_outputs": stale_outputs,
        "boundary": "Analytical macro toolkit display only; not a formal MTR metric, trade order, or portfolio execution engine.",
        "source_trace": _hason_source_trace(modules, scripts_by_name),
    }


def _hason_runtime_outputs(
    output_files: list[dict[str, object]],
    *,
    analysis_date: str | None,
) -> list[dict[str, object]]:
    files_by_name = {str(item["name"]): item for item in output_files}
    return [
        _hason_runtime_output_payload(name, files_by_name.get(name), analysis_date=analysis_date)
        for name in _HASON_REQUIRED_OUTPUTS
    ]


def _hason_runtime_output_payload(
    name: str,
    file_payload: dict[str, object] | None,
    *,
    analysis_date: str | None,
) -> dict[str, object]:
    if file_payload is None:
        return {
            "name": name,
            "freshness_status": "missing",
            "freshness_basis": "missing",
            "modified_at": None,
            "modified_date": None,
            "content_date": None,
            "content_date_min": None,
            "content_date_max": None,
            "content_date_invalid_count": 0,
            "reference_date": analysis_date,
        }
    modified_at = str(file_payload.get("modified_at") or "").strip() or None
    modified_date = _hason_output_modified_date(modified_at)
    content_dates = _hason_output_content_dates(file_payload)
    content_date = content_dates["max"]
    content_date_min = content_dates["min"]
    content_date_max = content_dates["max"]
    content_date_invalid_count = int(content_dates["invalid_count"] or 0)
    has_content_date_column = bool(content_dates["date_column"])
    freshness_basis = "csv_content" if has_content_date_column else "file_modified_date"
    freshness_status = (
        "invalid_date"
        if content_date_invalid_count
        else "mixed"
        if content_date_min and content_date_max and content_date_min != content_date_max
        else "unknown"
        if has_content_date_column and not content_date
        else _hason_output_freshness(content_date or modified_date, analysis_date)
    )
    return {
        "name": name,
        "freshness_status": freshness_status,
        "freshness_basis": freshness_basis,
        "modified_at": modified_at,
        "modified_date": modified_date,
        "content_date": content_date,
        "content_date_min": content_date_min,
        "content_date_max": content_date_max,
        "content_date_invalid_count": content_date_invalid_count,
        "reference_date": analysis_date,
    }


def _hason_output_modified_date(modified_at: str | None) -> str | None:
    if not modified_at:
        return None
    try:
        parsed = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(_HASON_BUSINESS_TZ).date().isoformat()


def _hason_output_content_dates(file_payload: dict[str, object]) -> dict[str, str | int | None]:
    path_value = file_payload.get("path")
    if not path_value:
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    path = Path(str(path_value))
    if not path.is_file():
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    try:
        columns = pd.read_csv(path, nrows=0).columns
        date_column = next((column for column in _HASON_OUTPUT_DATE_COLUMNS if column in columns), None)
        if date_column is None:
            return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
        frame = pd.read_csv(path, usecols=[date_column])
    except (OSError, UnicodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    if frame.empty:
        return {"min": None, "max": None, "invalid_count": 0, "date_column": date_column}
    raw_dates = frame[date_column].dropna()
    parsed = pd.to_datetime(raw_dates, errors="coerce")
    invalid_count = int(parsed.isna().sum())
    parsed = parsed.dropna()
    if parsed.empty:
        return {"min": None, "max": None, "invalid_count": invalid_count, "date_column": date_column}
    return {
        "min": parsed.min().date().isoformat(),
        "max": parsed.max().date().isoformat(),
        "invalid_count": invalid_count,
        "date_column": date_column,
    }


def _hason_output_freshness(modified_date: str | None, analysis_date: str | None) -> str:
    if not modified_date:
        return "unknown"
    if not analysis_date:
        return "present"
    try:
        modified = date.fromisoformat(modified_date[:10])
        reference = date.fromisoformat(analysis_date[:10])
    except ValueError:
        return "unknown"
    if modified > reference:
        return "future"
    return "current" if modified == reference else "stale"


def _hason_runtime_output_status(runtime_outputs: list[dict[str, object]]) -> str:
    statuses = {str(item["freshness_status"]) for item in runtime_outputs}
    if "missing" in statuses:
        return "missing"
    if "stale" in statuses:
        return "stale"
    if "unknown" in statuses or "future" in statuses or "mixed" in statuses or "invalid_date" in statuses:
        return "unknown"
    if statuses == {"current"}:
        return "current"
    return "present"


def _hason_module_payload(
    module: dict[str, object],
    scripts_by_name: dict[str, MacroToolkitScript],
) -> dict[str, object]:
    script_names = [str(name) for name in module["scripts"]]
    available = [name for name in script_names if scripts_by_name.get(name) and scripts_by_name[name].path.exists()]
    missing = [name for name in script_names if name not in available]
    status = "integrated" if not missing else "partial" if available else "missing"
    return {
        "key": module["key"],
        "label": module["label"],
        "status": status,
        "scripts": script_names,
        "available_scripts": available,
        "missing_scripts": missing,
        "evidence": list(module["evidence"]),
    }


def _hason_source_trace(
    modules: list[dict[str, object]],
    scripts_by_name: dict[str, MacroToolkitScript],
) -> list[dict[str, object]]:
    traced: list[dict[str, object]] = []
    seen: set[str] = set()
    module_keys_by_script: dict[str, list[str]] = {}
    for module in modules:
        module_key = str(module["key"])
        for script_name in module["scripts"]:
            module_keys_by_script.setdefault(str(script_name), []).append(module_key)
    for module in modules:
        for script_name in module["scripts"]:
            name = str(script_name)
            if name in seen:
                continue
            seen.add(name)
            script = scripts_by_name.get(name)
            traced.append(
                {
                    "script": name,
                    "filename": script.filename if script else None,
                    "group": script.group if script else None,
                    "available": bool(script and script.path.exists()),
                    "modules": module_keys_by_script.get(name, []),
                }
            )
    return traced


def _a_share_stampede_risk_card(a_share_risk: dict[str, object] | None) -> dict[str, object]:
    if not a_share_risk or a_share_risk.get("status") == "unavailable":
        warnings = a_share_risk.get("warnings") if isinstance(a_share_risk, dict) else []
        return _signal_card(
            "a_share_stampede_risk",
            "市场踩踏风险",
            "数据不足",
            "missing",
            None,
            [str(item) for item in warnings[:3]] if isinstance(warnings, list) else ["股票日线读面未命中"],
        )
    level = str(a_share_risk.get("risk_level") or "unknown")
    tone_by_level = {
        "green": "positive",
        "yellow": "neutral",
        "orange": "negative",
        "red": "negative",
        "unknown": "missing",
    }
    score = _float_or_none(a_share_risk.get("risk_score"))
    triggered = a_share_risk.get("triggered_rules") if isinstance(a_share_risk.get("triggered_rules"), list) else []
    warnings = a_share_risk.get("warnings") if isinstance(a_share_risk.get("warnings"), list) else []
    evidence = [str(item) for item in [*triggered[:2], *warnings[:1]]]
    if not evidence and a_share_risk.get("summary"):
        evidence = [str(a_share_risk["summary"])]
    return _signal_card(
        "a_share_stampede_risk",
        "市场踩踏风险",
        str(a_share_risk.get("risk_name") or level),
        tone_by_level.get(level, "missing"),
        round(score, 2) if score is not None else None,
        evidence,
    )


def _crisis_score_card(capability_results: list[dict[str, object]], *, deferred: bool = False) -> dict[str, object]:
    crisis = next((item for item in capability_results if item.get("key") == "crisis_score_cn"), None)
    if crisis is None:
        if deferred:
            return _signal_card(
                "crisis_score_cn",
                "Crisis Score",
                "完整结果待加载",
                "neutral",
                None,
                ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"],
            )
        return _signal_card("crisis_score_cn", "Crisis Score", "数据不足", "missing", None, ["Crisis Score 未接入"])
    result = crisis.get("result") if isinstance(crisis.get("result"), dict) else {}
    score = _float_or_none(crisis.get("score"))
    regime = str(result.get("regime") or crisis.get("headline") or "数据不足")
    evidence = crisis.get("evidence") if isinstance(crisis.get("evidence"), list) else []
    warnings = crisis.get("warnings") if isinstance(crisis.get("warnings"), list) else []
    return _signal_card(
        "crisis_score_cn",
        "Crisis Score",
        regime,
        str(crisis.get("tone") or "neutral"),
        round(score, 2) if score is not None else None,
        [str(item) for item in (evidence or warnings)[:3]],
    )


def _liquidity_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    dr007 = _number(indicator_by_key.get("dr007"), "latest_value")
    ncd = _number(indicator_by_key.get("ncd_3m"), "latest_value")
    if dr007 is None and ncd is None:
        return _signal_card("liquidity", "流动性", "数据不足", "missing", None, ["DR007 / 3M NCD 未命中"])
    anchor = dr007 if dr007 is not None else ncd
    assert anchor is not None
    if anchor <= 1.9:
        stance, tone, score = "偏松", "positive", 78
    elif anchor >= 2.3:
        stance, tone, score = "偏紧", "negative", 32
    else:
        stance, tone, score = "中性", "neutral", 55
    evidence = []
    if dr007 is not None:
        evidence.append(f"DR007 {dr007:.2f}%")
    if ncd is not None:
        evidence.append(f"3M NCD {ncd:.2f}%")
    return _signal_card("liquidity", "流动性", stance, tone, score, evidence)


def _risk_appetite_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    hs300_change = _number(indicator_by_key.get("hs300"), "change_pct")
    copper_change = _number(indicator_by_key.get("copper"), "change_pct")
    values = [item for item in (hs300_change, copper_change) if item is not None]
    if not values:
        return _signal_card("risk_appetite", "风险偏好", "数据不足", "missing", None, ["权益 / 工业品缺少可比较序列"])
    average = sum(values) / len(values)
    if average > 0.5:
        stance, tone, score = "改善", "positive", 72
    elif average < -0.5:
        stance, tone, score = "转弱", "negative", 35
    else:
        stance, tone, score = "震荡", "neutral", 52
    evidence = []
    if hs300_change is not None:
        evidence.append(f"沪深300 {hs300_change:+.2f}%")
    if copper_change is not None:
        evidence.append(f"铜主力 {copper_change:+.2f}%")
    return _signal_card("risk_appetite", "风险偏好", stance, tone, score, evidence)


def _credit_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    gov_5y = _number(indicator_by_key.get("gov_5y"), "latest_value")
    aa_5y = _number(indicator_by_key.get("aa_5y"), "latest_value")
    if gov_5y is None or aa_5y is None:
        return _signal_card("credit", "信用利差", "数据不足", "missing", None, ["5Y 国债 / 5Y AA 信用债未同时命中"])
    spread_bp = (aa_5y - gov_5y) * 100
    if spread_bp >= 90:
        stance, tone, score = "偏宽", "negative", 38
    elif spread_bp <= 45:
        stance, tone, score = "偏窄", "positive", 70
    else:
        stance, tone, score = "中性", "neutral", 55
    return _signal_card("credit", "信用利差", stance, tone, score, [f"AA-国债 5Y {spread_bp:.1f}bp"])


def _script_output_card(output_files: list[dict[str, object]]) -> dict[str, object]:
    if output_files:
        latest = max(output_files, key=lambda item: str(item["modified_at"]))
        return _signal_card(
            "outputs",
            "脚本产物",
            "已生成",
            "positive",
            min(100, 45 + len(output_files) * 5),
            [f"{len(output_files)} 个输出文件", str(latest["name"])],
        )
    return _signal_card(
        "outputs",
        "脚本产物",
        "待生成",
        "neutral",
        45,
        ["尚未在 data/macro_toolkit/output 发现输出文件"],
    )


def _signal_card(
    key: str,
    title: str,
    stance: str,
    tone: str,
    score: int | None,
    evidence: list[str],
) -> dict[str, object]:
    return {
        "key": key,
        "title": title,
        "stance": stance,
        "tone": tone,
        "score": score,
        "evidence": evidence,
    }


def _analysis_conclusion(
    signal_cards: list[dict[str, object]],
    coverage: dict[str, object],
) -> dict[str, object]:
    hit_rate = float(coverage["hit_rate"])
    if hit_rate < 0.6:
        return {
            "stance": "数据不足",
            "tone": "missing",
            "summary": "核心指标命中不足，当前页面只展示可用证据，不形成完整方向判断。",
            "recommended_action": "先补齐缺失的 Choice/Tushare 序列，再运行信号脚本。",
        }

    tones = [str(card["tone"]) for card in signal_cards if card["tone"] != "missing"]
    positive = tones.count("positive")
    negative = tones.count("negative")
    if positive > negative:
        stance, tone = "中性偏积极", "positive"
        summary = "流动性、风险资产或信用信号中积极证据更多，宏观环境暂不构成明显风险压制。"
        action = "维持观察，可优先运行 signal_aggregator / risk_monitor 形成交易层信号。"
    elif negative > positive:
        stance, tone = "中性偏谨慎", "negative"
        summary = "偏紧、转弱或信用压力信号占优，宏观环境需要降低冒进判断。"
        action = "先复核利率、信用和风险偏好序列，再做仓位或组合动作。"
    else:
        stance, tone = "中性观察", "neutral"
        summary = "多空证据接近，当前更适合观察数据延续性，而不是给出单边结论。"
        action = "关注下一批 Choice/Tushare 更新，并运行信号聚合脚本确认。"
    return {"stance": stance, "tone": tone, "summary": summary, "recommended_action": action}


def _analysis_warnings(coverage: dict[str, object]) -> list[str]:
    if float(coverage["hit_rate"]) < 0.6:
        return ["核心宏观指标命中不足，当前结论只展示可用证据，不形成完整方向判断。"]
    return []


def _analysis_data_health(
    *,
    indicators: list[dict[str, object]],
    source_checks: list[dict[str, object]],
    capability_results: list[dict[str, object]],
    capabilities: list[dict[str, object]],
    runtime_status: dict[str, object],
    warnings: list[str],
    reference_date: str | None,
) -> dict[str, object]:
    deferred_sections = [
        str(section["key"])
        for section in runtime_status.get("deferred_sections", [])
        if isinstance(section, dict) and section.get("key")
    ]
    analysis_scope = str(runtime_status.get("analysis_scope") or "")
    return {
        "analysis_scope": runtime_status.get("analysis_scope"),
        "indicator_coverage": _indicator_data_health(indicators),
        "source_coverage": _source_data_health(
            source_checks,
            deferred="source_checks" in deferred_sections,
        ),
        "capability_results": _capability_result_data_health(
            capability_results,
            deferred="capability_results" in deferred_sections,
        ),
        "capability_plan": _capability_plan_data_health(
            capabilities,
            deferred="capabilities" in deferred_sections,
        ),
        "deferred_sections": deferred_sections,
        "repair_items": _analysis_repair_items(
            indicators=indicators,
            source_checks=source_checks,
            capability_results=capability_results,
            deferred_sections=deferred_sections,
            analysis_scope=analysis_scope,
            reference_date=reference_date,
        ),
        "warnings": warnings,
    }


def _analysis_repair_items(
    *,
    indicators: list[dict[str, object]],
    source_checks: list[dict[str, object]],
    capability_results: list[dict[str, object]],
    deferred_sections: list[str],
    analysis_scope: str,
    reference_date: str | None,
) -> list[dict[str, object]]:
    missing_indicator_aliases = {
        str(item.get("alias"))
        for item in indicators
        if item.get("alias") and item.get("latest_value") is None
    }
    items: list[dict[str, object]] = [
        _missing_indicator_repair_item(item, analysis_scope=analysis_scope, reference_date=reference_date)
        for item in indicators
        if item.get("latest_value") is None
    ]

    if "source_checks" not in deferred_sections:
        items.extend(
            _source_repair_item(check, analysis_scope=analysis_scope, reference_date=reference_date)
            for check in source_checks
            if _source_check_needs_repair(check, reference_date)
            and str(check.get("alias") or "") not in missing_indicator_aliases
        )

    if "capability_results" not in deferred_sections:
        items.extend(
            _capability_repair_item(item, analysis_scope=analysis_scope, reference_date=reference_date)
            for item in capability_results
            if str(item.get("status") or "") in {"degraded", "unavailable"}
        )

    items.extend(
        _deferred_repair_item(section, analysis_scope=analysis_scope, reference_date=reference_date)
        for section in deferred_sections
        if section in {"source_checks", "capability_results", "capabilities"}
    )
    return sorted(items, key=_repair_item_sort_key)


def _missing_indicator_repair_item(
    item: dict[str, object],
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    alias = str(item.get("alias") or "")
    label = str(item.get("label") or item.get("key") or alias)
    return {
        "type": "missing",
        "scope": analysis_scope,
        "priority": "high",
        "key": f"indicator:{item.get('key')}",
        "alias": alias or None,
        "label": label,
        "source_table": None,
        "latest_date": None,
        "reference_date": reference_date,
        "stale_days": None,
        "suggested_action": f"补齐 {alias or label} 后重新运行完整宏观分析；缺失项不能按 0 处理。",
        "action": _source_backfill_action("需要补齐来源数据", alias=alias),
        "tags": ["indicator"],
    }


def _source_check_needs_repair(check: dict[str, object], reference_date: str | None) -> bool:
    if int(check.get("row_count") or 0) <= 0:
        return True
    latest = check.get("latest")
    if not isinstance(latest, dict):
        return True
    if str(check.get("alias") or "") not in _DAILY_SOURCE_CHECK_ALIASES:
        return False
    return _stale_days(latest.get("date"), reference_date) is not None


def _source_repair_item(
    check: dict[str, object],
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    alias = str(check.get("alias") or "")
    latest = check.get("latest") if isinstance(check.get("latest"), dict) else None
    latest_date = str(latest.get("date"))[:10] if isinstance(latest, dict) and latest.get("date") else None
    stale_days = _stale_days(latest_date, reference_date)
    if int(check.get("row_count") or 0) <= 0 or latest is None:
        return {
            "type": "missing",
            "scope": analysis_scope,
            "priority": "high",
            "key": f"source:{alias}",
            "alias": alias or None,
            "label": alias,
            "source_table": "system_macro_sources",
            "latest_date": None,
            "reference_date": reference_date,
            "stale_days": None,
            "suggested_action": f"补齐 {alias} 来源数据后重新运行完整宏观分析；缺失项不能按 0 处理。",
            "action": _source_backfill_action("需要补齐来源数据", alias=alias),
            "tags": ["source"],
        }
    return {
        "type": "stale",
        "scope": analysis_scope,
        "priority": "medium",
        "key": f"source:{alias}",
        "alias": alias or None,
        "label": alias,
        "source_table": "system_macro_sources",
        "latest_date": latest_date,
        "reference_date": reference_date,
        "stale_days": stale_days,
        "suggested_action": (
            f"{alias} 最新 {latest_date}，落后分析日 {reference_date} {stale_days} 天；"
            "刷新 Choice/Tushare 后再确认。"
        ),
        "action": _source_backfill_action("需要刷新来源", alias=alias),
        "tags": ["source"],
    }


def _capability_repair_item(
    item: dict[str, object],
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    key = str(item.get("key") or "")
    status = str(item.get("status") or "")
    warnings = [str(warning) for warning in item.get("warnings", []) if warning]
    priority = "high" if status == "unavailable" else "medium"
    label = str(item.get("label") or key)
    warning_text = " / ".join(warnings[:3])
    reason = warning_text or status
    return {
        "type": "missing" if status == "unavailable" else "degraded",
        "scope": analysis_scope,
        "priority": priority,
        "key": f"capability:{key}",
        "alias": None,
        "label": label,
        "source_table": None,
        "latest_date": None,
        "reference_date": reference_date,
        "stale_days": None,
        "suggested_action": f"{label} 当前 {status}：{reason}；补齐输入证据后重新运行完整宏观分析。",
        "action": _full_analysis_action(
            label="重新完整分析",
            reason="补齐输入证据后重新运行完整分析确认状态。",
        ),
        "tags": ["capability"],
    }


def _deferred_repair_item(
    section: str,
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    return {
        "type": "deferred",
        "scope": analysis_scope,
        "priority": "low",
        "key": f"deferred:{section}",
        "alias": None,
        "label": section,
        "source_table": None,
        "latest_date": None,
        "reference_date": reference_date,
        "stale_days": None,
        "suggested_action": f"打开完整分析后确认 {section}，不把首屏延后加载当作缺失。",
        "action": _full_analysis_action(
            label="查看完整分析",
            reason="首屏延后加载，完整分析可确认。",
        ),
        "tags": ["deferred"],
    }


def _source_backfill_action(label: str, *, alias: str | None = None) -> dict[str, object]:
    enabled = str(alias or "").strip().lower() in _SOURCE_BACKFILL_TARGETS
    return {
        "kind": "source_backfill_required",
        "label": label,
        "enabled": enabled,
        "reason": (
            "可触发宏观来源补齐；完成后重新运行完整分析确认。"
            if enabled
            else "当前没有已接入的一键宏观序列刷新接口。"
        ),
        "analysis_detail": "full",
    }


def _full_analysis_action(*, label: str, reason: str) -> dict[str, object]:
    return {
        "kind": "load_full_analysis",
        "label": label,
        "enabled": True,
        "reason": reason,
        "analysis_detail": "full",
    }


def _stale_days(latest_date: object, reference_date: str | None) -> int | None:
    if not latest_date or not reference_date:
        return None
    try:
        latest = date.fromisoformat(str(latest_date)[:10])
        reference = date.fromisoformat(str(reference_date)[:10])
    except ValueError:
        return None
    days = (reference - latest).days
    return days if days > 1 else None


def _repair_item_sort_key(item: dict[str, object]) -> tuple[int, str, str]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    type_order = {"missing": 0, "stale": 1, "degraded": 2, "deferred": 3}
    return (
        priority_order.get(str(item.get("priority")), 9),
        str(type_order.get(str(item.get("type")), 9)),
        str(item.get("key") or ""),
    )


def _indicator_data_health(indicators: list[dict[str, object]]) -> dict[str, object]:
    hit_count = sum(1 for item in indicators if item.get("latest_value") is not None)
    missing = [
        {
            "key": item.get("key"),
            "alias": item.get("alias"),
            "label": item.get("label"),
        }
        for item in indicators
        if item.get("latest_value") is None
    ]
    return {
        "hit_count": hit_count,
        "total_count": len(indicators),
        "hit_rate": round(hit_count / len(indicators), 4) if indicators else None,
        "missing_count": len(missing),
        "missing": missing,
    }


def _source_data_health(
    source_checks: list[dict[str, object]],
    *,
    deferred: bool,
) -> dict[str, object]:
    hit_count = sum(1 for item in source_checks if int(item.get("row_count") or 0) > 0)
    missing_aliases = [
        str(item["alias"])
        for item in source_checks
        if item.get("alias") and int(item.get("row_count") or 0) <= 0
    ]
    return {
        "hit_count": hit_count,
        "total_count": len(source_checks),
        "hit_rate": round(hit_count / len(source_checks), 4) if source_checks else None,
        "latest_date": _latest_source_check_date(source_checks),
        "deferred": deferred,
        "missing_aliases": missing_aliases,
    }


def _capability_result_data_health(
    capability_results: list[dict[str, object]],
    *,
    deferred: bool,
) -> dict[str, object]:
    return {
        "complete": sum(1 for item in capability_results if item.get("status") == "complete"),
        "degraded": sum(1 for item in capability_results if item.get("status") == "degraded"),
        "unavailable": sum(1 for item in capability_results if item.get("status") == "unavailable"),
        "total_count": len(capability_results),
        "deferred": deferred,
    }


def _capability_plan_data_health(
    capabilities: list[dict[str, object]],
    *,
    deferred: bool,
) -> dict[str, object]:
    ready_count = sum(1 for item in capabilities if str(item.get("data_status")) == "ready")
    wired_count = sum(
        1
        for item in capabilities
        if str(item.get("route_status")) == "wired" and str(item.get("frontend_status")) == "visible"
    )
    return {
        "ready_count": ready_count,
        "wired_count": wired_count,
        "total_count": len(capabilities),
        "deferred": deferred,
    }


def _analysis_runtime_status(scope: str) -> dict[str, object]:
    deferred_sections = []
    if scope == "core":
        deferred_sections = [
            {
                "key": "capability_results",
                "label": "M7-M16 功能结果",
                "status": "deferred",
            },
            {
                "key": "strategy_summaries",
                "label": "策略展示",
                "status": "deferred",
            },
            {
                "key": "a_share_risk",
                "label": "市场踩踏风险",
                "status": "deferred",
            },
            {
                "key": "source_checks",
                "label": "系统数据源命中",
                "status": "deferred",
            },
            {
                "key": "capabilities",
                "label": "功能补齐方案",
                "status": "deferred",
            },
        ]
    return {
        "analysis_scope": scope,
        "deferred_sections": deferred_sections,
    }


def _latest_indicator_date(indicators: list[dict[str, object]]) -> str | None:
    dates = [str(item["latest_date"]) for item in indicators if item["latest_date"]]
    return max(dates) if dates else None


def _latest_strategy_as_of_date(strategies: list[dict[str, object]]) -> str | None:
    dates: list[str] = []
    for strategy in strategies:
        result = strategy.get("result")
        if not isinstance(result, dict):
            continue
        for key in ("as_of_date", "factor_as_of_date"):
            value = str(result.get(key) or "").strip()
            if value:
                dates.append(value[:10])
    return max(dates) if dates else None


def _number(item: dict[str, object] | None, field: str) -> float | None:
    if item is None or item.get(field) is None:
        return None
    return float(item[field])


def _envelope(
    result_kind: str,
    result: dict[str, object],
    *,
    quality_flag: str | None = None,
    fallback_mode: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, object]:
    generated_at = datetime.now(UTC).isoformat()
    tables_used = [
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "fx_daily_mid",
        "fact_formal_yield_curve_daily",
        "std_external_macro_daily",
        "fact_commodity_futures_daily",
        "fact_cffex_member_rank_daily",
        "vw_cffex_member_rank_daily",
    ]
    if "capability_results" in result:
        tables_used.extend(
            [
                "fact_formal_risk_tensor_daily",
                "fact_formal_bond_analytics_daily",
            ]
        )
    if _strategy_summaries_use_choice_stock(result):
        tables_used.append("choice_stock_daily_observation")
    if _strategy_summaries_use_stock_factor_snapshot(result):
        tables_used.append("choice_stock_factor_snapshot")
    shadow_report = result.get("shadow_portfolio_report")
    if isinstance(shadow_report, dict):
        report_tables = shadow_report.get("tables_used")
        if isinstance(report_tables, list):
            tables_used.extend(str(table) for table in report_tables)
    if "choice_stock_refresh" in result:
        tables_used.extend(["choice_stock_daily_observation", "choice_stock_factor_snapshot"])
    a_share_risk = result.get("a_share_risk")
    if isinstance(a_share_risk, dict):
        risk_tables = a_share_risk.get("tables_used")
        if isinstance(risk_tables, list):
            tables_used.extend(str(table) for table in risk_tables)
    return build_result_envelope(
        basis="analytical",
        trace_id=f"macro-toolkit-{uuid.uuid4().hex[:12]}",
        result_kind=result_kind,
        cache_version="none",
        source_version="macro_toolkit_registry",
        rule_version="rv_macro_toolkit_ui_v1",
        result_payload=result,
        quality_flag=quality_flag or "ok",
        vendor_version="choice+tushare",
        vendor_status="ok",
        fallback_mode=fallback_mode or "none",
        tables_used=_unique_texts(tables_used),
        evidence_rows=_evidence_rows(result),
        as_of_date=as_of_date,
        generated_at=generated_at,
    )


def _evidence_rows(result: dict[str, object]) -> int | None:
    for key in ("scripts", "indicators"):
        value = result.get(key)
        if isinstance(value, list):
            return len(value)
    return None


def _strategy_summaries_use_choice_stock(result: dict[str, object]) -> bool:
    summaries = result.get("strategy_summaries")
    if not isinstance(summaries, list):
        return False
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        detail = summary.get("result")
        if isinstance(detail, dict) and detail.get("price_source") == "choice_stock_daily_observation":
            return True
    return False


def _strategy_summaries_use_stock_factor_snapshot(result: dict[str, object]) -> bool:
    summaries = result.get("strategy_summaries")
    if not isinstance(summaries, list):
        return False
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        detail = summary.get("result")
        if isinstance(detail, dict) and detail.get("factor_source") == "choice_stock_factor_snapshot":
            return True
    return False
