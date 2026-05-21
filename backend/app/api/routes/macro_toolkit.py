from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import duckdb
import pandas as pd
from backend.app.core_finance.macro import (
    analyze_cross_market_linkage,
    classify_low_crowding_market_regime,
    compute_credit_spread_risk,
    compute_crisis_score_payload,
    compute_economic_cycle,
    compute_leading_indicator,
    compute_liquidity_stress_test,
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
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import DEFAULT_CFFEX_CONTRACTS, table_stats
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import macro_adversarial_signal_service, macro_toolkit_service
from backend.app.services.formal_result_runtime import build_result_envelope
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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


class CffexMemberRankRefreshRequest(BaseModel):
    trade_date: str | None = None
    contracts: list[str] = Field(default_factory=lambda: list(DEFAULT_CFFEX_CONTRACTS))
    sources: list[str] = Field(default_factory=lambda: ["choice", "tushare"])


class ChoiceStockRefreshRequest(BaseModel):
    as_of_date: str | None = None
    refresh_history: bool = True
    refresh_factors: bool = True
    factor_max_stock_count: int | None = Field(default=None, ge=1)


@router.get("/scripts")
def macro_toolkit_scripts() -> dict[str, object]:
    settings = get_settings()
    scripts = [_script_payload(script) for script in iter_toolkit_scripts()]
    source_checks = _source_checks(settings.duckdb_path)
    cffex_status = _cffex_member_rank_status(
        settings.duckdb_path,
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
            "capabilities": _capability_plan(settings.duckdb_path),
            "cffex_member_rank": cffex_status,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
            ),
            "warnings": _script_warnings(cffex_status),
        },
    )


@router.get("/analysis")
def macro_toolkit_analysis() -> dict[str, object]:
    settings = get_settings()
    indicators = _analysis_indicators(settings.duckdb_path)
    indicator_by_key = {str(item["key"]): item for item in indicators}
    output_files = _output_files()
    analysis_date = _latest_indicator_date(indicators)
    capability_results = _macro_capability_results(
        settings.duckdb_path,
        report_date=analysis_date,
    )
    a_share_risk = _a_share_stampede_risk(settings.duckdb_path)
    signal_cards = _analysis_signal_cards(
        indicator_by_key,
        output_files,
        capability_results,
        a_share_risk,
    )
    hit_count = sum(1 for item in indicators if item["latest_value"] is not None)
    coverage = {
        "indicator_count": len(indicators),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(indicators), 4) if indicators else 0,
        "script_count": len(iter_toolkit_scripts()),
        "output_file_count": len(output_files),
    }
    conclusion = _analysis_conclusion(signal_cards, coverage)
    return _envelope(
        "macro_toolkit.analysis",
        {
            "default_data_sources": list(DEFAULT_DATA_SOURCES),
            "as_of_date": analysis_date,
            "conclusion": conclusion,
            "coverage": coverage,
            "indicators": indicators,
            "signal_cards": signal_cards,
            "a_share_risk": a_share_risk,
            "capability_results": capability_results,
            "strategy_summaries": _equity_strategy_summaries(settings.duckdb_path),
            "output_files": output_files,
            "source_checks": _source_checks(settings.duckdb_path),
            "capabilities": _capability_plan(settings.duckdb_path),
            "cffex_member_rank": _cffex_member_rank_status(
                settings.duckdb_path,
                reference_date=_latest_indicator_date(indicators),
            ),
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
            ),
            "warnings": _analysis_warnings(coverage),
        },
    )


@router.get("/adversarial-signal")
def macro_toolkit_adversarial_signal() -> dict[str, object]:
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
    request: ChoiceStockRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or ChoiceStockRefreshRequest()
    if not refresh_request.refresh_history and not refresh_request.refresh_factors:
        raise HTTPException(
            status_code=400,
            detail="At least one of refresh_history or refresh_factors must be true.",
        )

    settings = get_settings()
    as_of_date = refresh_request.as_of_date or _default_choice_stock_refresh_as_of_date(settings.duckdb_path)
    permission = _choice_stock_refresh_permission_payload(auth)
    try:
        refresh = macro_toolkit_service.queue_choice_stock_refresh(
            background_tasks=background_tasks,
            duckdb_path=str(settings.duckdb_path),
            catalog_path=str(settings.choice_stock_catalog_file),
            governance_path=str(settings.governance_path),
            as_of_date=as_of_date,
            refresh_history=refresh_request.refresh_history,
            refresh_factors=refresh_request.refresh_factors,
            factor_max_stock_count=refresh_request.factor_max_stock_count,
            permission=permission,
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
            ),
        },
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.get("/choice-stock/refresh-status")
def macro_toolkit_choice_stock_refresh_status(run_id: str = Query(default="")) -> dict[str, object]:
    settings = get_settings()
    try:
        status = _choice_stock_refresh_status(settings.governance_path, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _envelope(
        "macro_toolkit.choice_stock_refresh_status",
        {
            "refresh": status,
            "choice_stock_refresh": _choice_stock_refresh_overview(settings.duckdb_path, settings.governance_path),
        },
    )


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
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    if not OUTPUT_DIR.exists():
        return []
    files: list[dict[str, object]] = []
    for path in sorted(OUTPUT_DIR.glob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            }
        )
    return files


def _source_checks(duckdb_path: str | Path) -> list[dict[str, object]]:
    return [_source_check(alias, duckdb_path) for alias in _SOURCE_CHECK_ALIASES]


def _source_check(alias: str, duckdb_path: str | Path, *, end: str | None = None) -> dict[str, object]:
    frame = load_series_by_alias(alias, end=end, duckdb_path=duckdb_path)
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
    history_row_count: int | None = None,
    factor_row_count: int | None = None,
    source_version: object | None = None,
    vendor_version: object | None = None,
    error_message: str | None = None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
    permission: dict[str, object] | None = None,
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
        history_row_count=history_row_count,
        factor_row_count=factor_row_count,
        source_version=source_version,
        vendor_version=vendor_version,
        error_message=error_message,
        failure_category=failure_category,
        failure_reason=failure_reason,
        permission=permission,
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


def _choice_stock_refresh_overview(
    duckdb_path: str | Path,
    governance_path: str | Path,
    *,
    permission: dict[str, object] | None = None,
) -> dict[str, object]:
    return macro_toolkit_service.choice_stock_refresh_overview(
        duckdb_path,
        governance_path,
        permission=permission,
    )


def _default_choice_stock_refresh_as_of_date(duckdb_path: str | Path) -> str:
    return macro_toolkit_service.default_choice_stock_refresh_as_of_date(duckdb_path)


def _capability_plan(duckdb_path: str | Path) -> list[dict[str, object]]:
    return [_capability_payload(item, duckdb_path) for item in _CAPABILITY_DEFINITIONS]


def _capability_payload(definition: dict[str, object], duckdb_path: str | Path) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in definition["data_aliases"])
    checks = [_source_check(alias, duckdb_path) for alias in aliases]
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
) -> list[dict[str, object]]:
    parsed_report_date = _parse_report_date(report_date)
    if parsed_report_date is None:
        return [_unavailable_capability_result(item, "缺少可用分析日期") for item in _CAPABILITY_DEFINITIONS]

    curve_rows = _load_macro_curve_rows(duckdb_path, parsed_report_date)
    wide_rows = _load_macro_wide_rows(duckdb_path, parsed_report_date, curve_rows)
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
            lambda: _compute_crisis_score_capability(duckdb_path, parsed_report_date),
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
    for key in ("monetary_policy_stance", "leading_indicator", "economic_cycle"):
        raw_results[key] = _with_capability_input_evidence(
            key,
            raw_results[key],
            duckdb_path=duckdb_path,
            report_date=parsed_report_date,
            wide_rows=wide_rows,
        )

    cards: list[dict[str, object]] = []
    for definition in _CAPABILITY_DEFINITIONS:
        if definition["key"] == "decision_summary":
            cards.append(_decision_summary_card(definition, cards, parsed_report_date))
            continue
        raw_result = raw_results.get(str(definition["key"]))
        cards.append(_capability_result_card(definition, raw_result))
    return cards


_EQUITY_PRICE_LOOKBACK_DAYS = 260
_EQUITY_PRICE_MIN_OBSERVATIONS = 80
_EQUITY_PRICE_MAX_STOCKS = 500
_A_SHARE_RISK_LOOKBACK_DAYS = 35
_A_SHARE_RISK_MAX_STOCKS = 8000


def _equity_strategy_summaries(duckdb_path: str | Path | None = None) -> list[dict[str, object]]:
    try:
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
        return [
            {
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
        ]


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
    if duckdb_path is None:
        return None
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        if not _duckdb_table_exists(conn, "choice_stock_daily_observation"):
            return None
        latest_row = conn.execute(
            """
            select max(try_cast(trade_date as date))
            from choice_stock_daily_observation
            where close_value is not null
              and close_value > 0
            """
        ).fetchone()
        latest_trade_date = latest_row[0] if latest_row else None
        if latest_trade_date is None:
            return None
        start_date = latest_trade_date - timedelta(days=_A_SHARE_RISK_LOOKBACK_DAYS)
        rows = conn.execute(
            f"""
            with latest_sample as (
              select stock_code
              from choice_stock_daily_observation
              where try_cast(trade_date as date) = ?
                and close_value is not null
                and close_value > 0
              order by coalesce(amount, 0) desc, stock_code asc
              limit {_A_SHARE_RISK_MAX_STOCKS}
            )
            select
              daily.try_cast_date as trade_date,
              daily.stock_code,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.amount,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              daily.tradestatus,
              try_cast(daily.highlimit as double) as highlimit,
              try_cast(daily.lowlimit as double) as lowlimit,
              daily.source_version,
              daily.vendor_version
            from (
              select
                try_cast(trade_date as date) as try_cast_date,
                stock_code,
                open_value,
                high_value,
                low_value,
                close_value,
                amount,
                pctchange,
                turn,
                amplitude,
                tradestatus,
                highlimit,
                lowlimit,
                source_version,
                vendor_version
              from choice_stock_daily_observation
            ) daily
            join latest_sample sample
              on sample.stock_code = daily.stock_code
            where daily.try_cast_date > ?
              and daily.try_cast_date <= ?
              and daily.close_value is not null
              and daily.close_value > 0
            order by daily.try_cast_date asc, daily.stock_code asc
            """,
            [latest_trade_date, start_date, latest_trade_date],
        ).fetchall()
        if not rows:
            return None
        observations = pd.DataFrame(
            rows,
            columns=[
                "trade_date",
                "stock_code",
                "open_value",
                "high_value",
                "low_value",
                "close_value",
                "amount",
                "pctchange",
                "turn",
                "amplitude",
                "tradestatus",
                "highlimit",
                "lowlimit",
                "source_version",
                "vendor_version",
            ],
        )
        tables_used = ["choice_stock_daily_observation"]
        warnings: list[str] = []
        _merge_a_share_universe(conn, observations, latest_trade_date, tables_used, warnings)
        _merge_a_share_limit_quality(conn, observations, latest_trade_date, tables_used)
        theme_frame = _load_a_share_theme_frame(conn, latest_trade_date, tables_used)
    except duckdb.Error:
        return None
    finally:
        conn.close()
    return {
        "observations": observations,
        "theme_frame": theme_frame,
        "tables_used": tables_used,
        "warnings": warnings,
    }


def _merge_a_share_universe(
    conn: duckdb.DuckDBPyConnection,
    observations: pd.DataFrame,
    latest_trade_date: date,
    tables_used: list[str],
    warnings: list[str],
) -> None:
    if not _duckdb_table_exists(conn, "choice_stock_universe"):
        warnings.append("choice_stock_universe 未命中，ST/北交所/新股过滤仅按日线字段能力降级判断。")
        return
    rows = conn.execute(
        """
        select stock_code, stock_name
        from choice_stock_universe
        where try_cast(as_of_date as date) = ?
        """,
        [latest_trade_date],
    ).fetchall()
    if not rows:
        warnings.append("choice_stock_universe 最新交易日无样本，ST/北交所/新股过滤按日线字段能力降级判断。")
        return
    universe = pd.DataFrame(rows, columns=["stock_code", "stock_name"])
    universe["is_st"] = universe["stock_name"].astype(str).str.contains("ST|退", case=False, regex=True, na=False)
    universe["is_bse"] = universe["stock_code"].astype(str).str.endswith((".BJ", ".BSE"))
    latest_mask = pd.to_datetime(observations["trade_date"]).dt.date == latest_trade_date
    merged = observations.loc[latest_mask, ["stock_code"]].merge(universe, on="stock_code", how="left")
    observations.loc[latest_mask, "stock_name"] = merged["stock_name"].to_numpy()
    observations.loc[latest_mask, "is_st"] = merged["is_st"].fillna(False).to_numpy()
    observations.loc[latest_mask, "is_bse"] = merged["is_bse"].fillna(False).to_numpy()
    observations["is_st"] = observations["is_st"].map(lambda value: False if pd.isna(value) else bool(value))
    observations["is_bse"] = observations["is_bse"].map(lambda value: False if pd.isna(value) else bool(value))
    observations["is_st"] = observations.groupby("stock_code")["is_st"].transform("max").astype(bool)
    observations["is_bse"] = observations.groupby("stock_code")["is_bse"].transform("max").astype(bool)
    tables_used.append("choice_stock_universe")


def _merge_a_share_limit_quality(
    conn: duckdb.DuckDBPyConnection,
    observations: pd.DataFrame,
    latest_trade_date: date,
    tables_used: list[str],
) -> None:
    if not _duckdb_table_exists(conn, "choice_stock_limit_quality"):
        return
    rows = conn.execute(
        """
        select stock_code, issurgedlimit, isdeclinelimit
        from choice_stock_limit_quality
        where try_cast(as_of_date as date) = ?
        """,
        [latest_trade_date],
    ).fetchall()
    if not rows:
        return
    quality = pd.DataFrame(rows, columns=["stock_code", "is_limit_up_flag", "is_limit_down_flag"])
    latest_mask = pd.to_datetime(observations["trade_date"]).dt.date == latest_trade_date
    merged = observations.loc[latest_mask, ["stock_code"]].merge(quality, on="stock_code", how="left")
    observations.loc[latest_mask, "is_limit_up_flag"] = merged["is_limit_up_flag"].to_numpy()
    observations.loc[latest_mask, "is_limit_down_flag"] = merged["is_limit_down_flag"].to_numpy()
    tables_used.append("choice_stock_limit_quality")


def _load_a_share_theme_frame(
    conn: duckdb.DuckDBPyConnection,
    latest_trade_date: date,
    tables_used: list[str],
) -> pd.DataFrame | None:
    if _duckdb_table_exists(conn, "choice_stock_factor_snapshot"):
        rows = conn.execute(
            """
            select stock_code, industry, three_month_return
            from choice_stock_factor_snapshot
            where try_cast(as_of_date as date) = ?
            """,
            [latest_trade_date],
        ).fetchall()
        if rows:
            tables_used.append("choice_stock_factor_snapshot")
            return pd.DataFrame(rows, columns=["stock_code", "industry", "three_month_return"])
    if _duckdb_table_exists(conn, "choice_stock_sector_membership"):
        rows = conn.execute(
            """
            select stock_code, sw2021 as industry
            from choice_stock_sector_membership
            where try_cast(as_of_date as date) = ?
            """,
            [latest_trade_date],
        ).fetchall()
        if rows:
            tables_used.append("choice_stock_sector_membership")
            return pd.DataFrame(rows, columns=["stock_code", "industry"])
    return None


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
        return {
            "key": "multi_factor_selection",
            "label": "多因子选股",
            "group": "A股策略",
            "status": "complete",
            "tone": "neutral",
            "primary_metric": {"label": "真实入选数量", "value": len(selected), "unit": ""},
            "evidence": [
                "已接入 choice_stock_factor_snapshot，按估值、质量、动量、低波动、股息五类因子打分。",
                f"因子快照日 {price_context['as_of_date']}，可用股票 {len(financials.index)} 只。",
            ],
            "warnings": [],
            "result": {
                "data_status": "complete",
                "price_source": "choice_stock_daily_observation",
                "factor_source": "choice_stock_factor_snapshot",
                "as_of_date": price_context["as_of_date"],
                "stock_count": len(prices.columns),
                "factor_row_count": len(financials.index),
                "selected_count": len(selected),
                "selected_stock_codes": selected_stock_codes,
                "selection_top_pct": 0.1,
                "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
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

    regime = classify_low_crowding_market_regime(prices, observations)
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

    selected = low_crowding_multifactor_selection(financials, observations)
    selected_stock_codes = [str(stock_code) for stock_code in selected.index.tolist()]
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
            f"因子快照 {price_context['as_of_date']}，低拥挤多因子入选 {len(selected_stock_codes)} 只。",
        ],
        "warnings": [],
        "result": {
            **base_result,
            "factor_source": "choice_stock_factor_snapshot",
            "factor_row_count": len(financials.index),
            "selected_count": len(selected_stock_codes),
            "selected_stock_codes": selected_stock_codes,
            "selection_top_pct": 0.1,
            "crowding_excluded_count": excluded_count,
            "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
        },
    }


def _load_equity_strategy_price_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    if duckdb_path is None:
        return None
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_stock_daily_observation" not in tables:
            return None
        latest_row = conn.execute(
            """
            select max(try_cast(trade_date as date))
            from choice_stock_daily_observation
            where close_value is not null
              and close_value > 0
            """
        ).fetchone()
        latest_trade_date = latest_row[0] if latest_row else None
        if latest_trade_date is None:
            return None
        start_date = latest_trade_date - timedelta(days=_EQUITY_PRICE_LOOKBACK_DAYS)
        rows = conn.execute(
            f"""
            with latest_sample as (
              select stock_code
              from choice_stock_daily_observation
              where try_cast(trade_date as date) = ?
                and close_value is not null
                and close_value > 0
              order by coalesce(amount, 0) desc, stock_code asc
              limit {_EQUITY_PRICE_MAX_STOCKS}
            )
            select
              daily.try_cast_date as trade_date,
              daily.stock_code,
              daily.close_value,
              daily.amount,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              daily.highlimit,
              daily.lowlimit,
              daily.source_version,
              daily.vendor_version
            from (
              select
                try_cast(trade_date as date) as try_cast_date,
                stock_code,
                close_value,
                amount,
                pctchange,
                turn,
                amplitude,
                highlimit,
                lowlimit,
                source_version,
                vendor_version
              from choice_stock_daily_observation
            ) daily
            join latest_sample sample
              on sample.stock_code = daily.stock_code
            where daily.try_cast_date > ?
              and daily.try_cast_date <= ?
              and daily.close_value is not null
              and daily.close_value > 0
            order by daily.try_cast_date asc, daily.stock_code asc
            """,
            [latest_trade_date, start_date, latest_trade_date],
        ).fetchall()
    except duckdb.Error:
        return None
    finally:
        conn.close()

    if not rows:
        return None
    frame = pd.DataFrame(
        rows,
        columns=[
            "trade_date",
            "stock_code",
            "close_value",
            "amount",
            "pctchange",
            "turn",
            "amplitude",
            "highlimit",
            "lowlimit",
            "source_version",
            "vendor_version",
        ],
    )
    prices = (
        frame.pivot_table(index="trade_date", columns="stock_code", values="close_value", aggfunc="last")
        .sort_index()
        .apply(pd.to_numeric, errors="coerce")
    )
    prices = prices.ffill().dropna(axis=1)
    prices = prices.loc[:, (prices > 0).all(axis=0)]
    if len(prices.index) < _EQUITY_PRICE_MIN_OBSERVATIONS or len(prices.columns) == 0:
        return None
    observations = frame[
        [
            "trade_date",
            "stock_code",
            "close_value",
            "amount",
            "pctchange",
            "turn",
            "amplitude",
            "highlimit",
            "lowlimit",
        ]
    ].copy()
    financials = _load_equity_strategy_factor_snapshot(path, latest_trade_date.isoformat())
    return {
        "prices": prices.astype("float64"),
        "observations": observations,
        "financials": financials,
        "as_of_date": latest_trade_date.isoformat(),
        "tables_used": [
            "choice_stock_daily_observation",
            *(["choice_stock_factor_snapshot"] if financials is not None else []),
        ],
        "source_versions": _unique_texts(frame["source_version"].tolist()),
        "vendor_versions": _unique_texts(frame["vendor_version"].tolist()),
    }


def _load_equity_strategy_factor_snapshot(
    duckdb_path: Path,
    as_of_date: str,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame | None:
    try:
        conn = duckdb.connect(str(duckdb_path), read_only=True)
    except duckdb.Error:
        return None
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_stock_factor_snapshot" not in tables:
            return None
        rows = conn.execute(
            """
            select
              stock_code,
              pe,
              pb,
              ps,
              roe,
              gross_margin,
              three_month_return,
              twelve_month_return,
              volatility,
              dividend_yield,
              industry
            from choice_stock_factor_snapshot
            where as_of_date = ?
            """,
            [as_of_date],
        ).fetchall()
    except duckdb.Error:
        return None
    finally:
        conn.close()
    if not rows:
        return None
    frame = pd.DataFrame(
        rows,
        columns=[
            "stock_code",
            "pe",
            "pb",
            "ps",
            "roe",
            "gross_margin",
            "three_month_return",
            "twelve_month_return",
            "volatility",
            "dividend_yield",
            "industry",
        ],
    )
    if stock_codes is not None:
        frame = frame[frame["stock_code"].isin(stock_codes)].copy()
    else:
        frame = frame.copy()
    if frame.empty:
        return None
    numeric_columns = list(REQUIRED_FACTOR_INPUTS)
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    frame["industry"] = frame["industry"].astype(str).str.strip()
    frame = frame.dropna(subset=numeric_columns + ["industry"])
    frame = frame[frame["industry"] != ""]
    if frame.empty:
        return None
    return frame.set_index("stock_code").sort_index()


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


def _compute_crisis_score_capability(duckdb_path: str | Path, report_date: date) -> dict[str, object]:
    start = report_date - timedelta(days=420)
    series_data: dict[str, list[tuple[date, float]]] = {}
    inputs: list[dict[str, object]] = []
    for config in _CRISIS_SCORE_INPUTS:
        alias = str(config["alias"])
        frame = load_series_by_alias(
            alias,
            start=start.isoformat(),
            end=report_date.isoformat(),
            duckdb_path=duckdb_path,
        )
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
    return enriched


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
) -> dict[str, object]:
    requirements = _CAPABILITY_INPUT_REQUIREMENTS.get(key)
    if not requirements:
        return result

    inputs = [
        _capability_input_evidence_item(requirement, duckdb_path=duckdb_path, report_date=report_date, wide_rows=wide_rows)
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
) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in requirement.get("aliases", ()))
    check = _first_available_source_check(aliases, duckdb_path, report_date)
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
) -> dict[str, object]:
    checks = [
        _source_check(alias, duckdb_path, end=report_date.isoformat())
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
    rows: list[dict[str, object]] = []
    path = Path(duckdb_path)
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            conn = None
        if conn is not None:
            try:
                if _duckdb_table_exists(conn, "fact_formal_yield_curve_daily"):
                    formal_rows = conn.execute(
                        """
                        select
                          cast(trade_date as varchar) as biz_date,
                          lower(curve_type) as curve_type,
                          tenor,
                          cast(rate_pct as double) as rate_value
                        from fact_formal_yield_curve_daily
                        where try_cast(trade_date as date) <= ?
                        """,
                        [report_date],
                    ).fetchall()
                    for biz_date, curve_type, tenor, rate_value in formal_rows:
                        curve_id = _CURVE_TYPE_TO_ID.get(str(curve_type))
                        if curve_id and rate_value is not None:
                            rows.append(
                                {
                                    "biz_date": str(biz_date)[:10],
                                    "curve_id": curve_id,
                                    "tenor": str(tenor),
                                    "rate_value": float(rate_value),
                                }
                            )
            finally:
                conn.close()

    for alias, curve_id, tenor in _CURVE_ALIAS_POINTS:
        frame = load_series_by_alias(alias, end=report_date.isoformat(), duckdb_path=duckdb_path)
        if frame.empty:
            continue
        for _, sample in frame.iterrows():
            sample_date = _coerce_frame_date(sample.get("date"))
            if sample_date is None or sample_date > report_date:
                continue
            value = _float_or_none(sample.get("value"))
            if value is None:
                continue
            rows.append(
                {
                    "biz_date": sample_date.isoformat(),
                    "curve_id": curve_id,
                    "tenor": tenor,
                    "rate_value": value,
                }
            )
    return rows


def _load_macro_wide_rows(
    duckdb_path: str | Path,
    report_date: date,
    curve_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    wide_by_date: dict[date, dict[str, float]] = {report_date: {}}
    fields = [field for field, _ in _WIDE_SERIES_ALIASES]
    for field, alias in _WIDE_SERIES_ALIASES:
        frame = load_series_by_alias(alias, end=report_date.isoformat(), duckdb_path=duckdb_path)
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
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        if not _duckdb_table_exists(conn, "fact_formal_risk_tensor_daily"):
            return None
        frame = conn.execute(
            """
            select *
            from fact_formal_risk_tensor_daily
            where try_cast(report_date as date) <= ?
            order by try_cast(report_date as date) desc
            limit 1
            """,
            [report_date],
        ).fetchdf()
    finally:
        conn.close()
    if frame.empty:
        return None
    return dict(frame.iloc[0])


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
    path = Path(duckdb_path)
    if not path.exists():
        return []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return []
    try:
        if not _duckdb_table_exists(conn, "fact_formal_bond_analytics_daily"):
            return []
        frame = conn.execute(
            """
            with latest as (
              select max(try_cast(report_date as date)) as report_date
              from fact_formal_bond_analytics_daily
              where try_cast(report_date as date) <= ?
            )
            select
              cast(market_value as double) as market_value,
              maturity_date,
              cast(coupon_rate as double) as coupon_rate
            from fact_formal_bond_analytics_daily, latest
            where try_cast(fact_formal_bond_analytics_daily.report_date as date) = latest.report_date
              and coalesce(cast(market_value as double), 0) > 0
            limit 5000
            """,
            [report_date],
        ).fetchdf()
    finally:
        conn.close()
    if frame.empty:
        return []
    positions: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        market_value = _float_or_none(row.get("market_value"))
        if market_value is None or market_value <= 0:
            continue
        positions.append(
            {
                "market_value": market_value,
                "maturity_date": _coerce_frame_date(row.get("maturity_date")),
                "coupon_rate": _float_or_none(row.get("coupon_rate")),
            }
        )
    return positions


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


def _duckdb_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()
    except duckdb.Error:
        return False
    return bool(row and row[0])


def _analysis_indicators(duckdb_path: str | Path) -> list[dict[str, object]]:
    indicators: list[dict[str, object]] = []
    for config in _ANALYSIS_INDICATORS:
        frame = load_series_by_alias(str(config["alias"]), duckdb_path=duckdb_path)
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
) -> list[dict[str, object]]:
    cards = [
        _crisis_score_card(capability_results),
        _a_share_stampede_risk_card(a_share_risk),
        _liquidity_card(indicator_by_key),
        _risk_appetite_card(indicator_by_key),
        _credit_card(indicator_by_key),
        _script_output_card(output_files),
    ]
    return cards


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


def _crisis_score_card(capability_results: list[dict[str, object]]) -> dict[str, object]:
    crisis = next((item for item in capability_results if item.get("key") == "crisis_score_cn"), None)
    if crisis is None:
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


def _latest_indicator_date(indicators: list[dict[str, object]]) -> str | None:
    dates = [str(item["latest_date"]) for item in indicators if item["latest_date"]]
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
