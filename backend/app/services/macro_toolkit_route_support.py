"""Macro toolkit route support layer.

Mechanically moved out of ``backend/app/api/routes/macro_toolkit.py`` so the
route module stays thin. The route module re-imports every public/private name
defined here into its own namespace, and endpoints keep calling unqualified
globals, so tests that monkeypatch attributes on the route module keep
working. This module must never import the route module (no import cycles).
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from backend.app.core_finance.data_freshness import (
    FRESHNESS_TIER_EXPIRED,
    FRESHNESS_TIER_STALE,
    assess_freshness,
)
from backend.app.core_finance.macro import (
    DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,  # noqa: F401  # re-exported for the route module
    analyze_cross_market_linkage,  # noqa: F401  # re-exported for the route module
    build_crisis_score_history_payload,  # noqa: F401  # re-exported for the route module
    classify_low_crowding_market_regime,
    clean_low_crowding_observations,
    compute_credit_spread_risk,  # noqa: F401  # re-exported for the route module
    compute_crisis_score_payload,  # noqa: F401  # re-exported for the route module
    compute_cta_trend_payload,  # noqa: F401  # re-exported for the route module
    compute_dcc_garch_payload,  # noqa: F401  # re-exported for the route module
    compute_economic_cycle,  # noqa: F401  # re-exported for the route module
    compute_leading_indicator,  # noqa: F401  # re-exported for the route module
    compute_liquidity_stress_test,  # noqa: F401  # re-exported for the route module
    compute_low_crowding_scores,
    compute_macro_portfolio_impact,  # noqa: F401  # re-exported for the route module
    compute_merrill_clock_payload,  # noqa: F401  # re-exported for the route module
    compute_monetary_policy_stance,  # noqa: F401  # re-exported for the route module
    compute_rate_turning_point,  # noqa: F401  # re-exported for the route module
    compute_risk_parity_payload,  # noqa: F401  # re-exported for the route module
    compute_yield_curve_shape,  # noqa: F401  # re-exported for the route module
    low_crowding_multifactor_selection,
    mean_reversion_momentum_strategy,
    moving_average_strategy,
    multi_factor_selection,
)
from backend.app.core_finance.macro.a_share_stampede_risk import (
    compute_a_share_stampede_risk,  # noqa: F401  # re-exported for the route module
    load_a_share_stampede_risk_config,  # noqa: F401  # re-exported for the route module
)
from backend.app.core_finance.macro.crisis_commodity_shadow import (
    evaluate_crisis_commodity_shadow,
)
from backend.app.core_finance.macro.equity_shadow_portfolio import (
    compute_equity_shadow_portfolio_report,  # noqa: F401  # re-exported for the route module
)
from backend.app.core_finance.macro.equity_strategies import REQUIRED_FACTOR_INPUTS
from backend.app.core_finance.macro.helpers import (
    build_curve_history,
    enrich_wide_with_curve_market_fields,
    sort_wide_rows_for_macro,
)
from backend.app.core_finance.macro.macro_portfolio_impact import (
    build_bond_portfolio_profile,  # noqa: F401  # re-exported for the route module
)
from backend.app.core_finance.macro.toolkit import (
    DEFAULT_DATA_SOURCES,  # noqa: F401  # re-exported for the route module
)
from backend.app.core_finance.macro.toolkit.paths import (
    OUTPUT_DIR,  # noqa: F401  # re-exported for the route module
)
from backend.app.core_finance.macro.toolkit.runner import (
    OMITTED_SOURCE_SCRIPTS,  # noqa: F401  # re-exported for the route module
    TOOLKIT_ROOT,
    MacroToolkitScript,
    iter_toolkit_scripts,  # noqa: F401  # re-exported for the route module
)
from backend.app.core_finance.macro.toolkit.system_sources import (
    clear_system_macro_source_cache,  # noqa: F401  # re-exported for the route module
    load_series_by_alias,
    load_series_by_aliases,
)
from backend.app.governance.settings import _REPO_ROOT
from backend.app.repositories.cffex_member_rank_repo import table_stats
from backend.app.security.auth_context import AuthContext, ensure_user_allowed
from backend.app.services import (
    macro_etf_strategy_service,
    macro_toolkit_refresh_receipt_service,
    macro_toolkit_service,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.macro_toolkit_analysis_service import (
    _a_share_stampede_risk_card,
    _credit_card,
    _crisis_commodity_candidate_decision,
    _crisis_commodity_candidate_summary,
    _crisis_score_card,
    _float_or_none,
    _liquidity_card,
    _metric,
    _risk_appetite_card,
    _script_output_card,
    _unique_sorted_texts,
    _unique_texts,
)
from backend.app.services.macro_toolkit_presentation import (
    _coerce_frame_date,
    _commodity_status_int,
    _commodity_status_text_set,
    _factor_snapshot_as_of_date,
    _factor_snapshot_date_status,
    _factor_snapshot_date_warnings,
    _factor_snapshot_provenance,
    _parse_report_date,
)

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

_DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS = macro_toolkit_service.DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS


def _macro_commodity_product_codes() -> frozenset[str]:
    # 延迟导入：commodity_daily_ingest 模块级 register_actor，冷启动不得触达。
    from backend.app.tasks.commodity_daily_ingest import COMMODITY_PRODUCTS

    return frozenset(spec.product_code.upper() for spec in COMMODITY_PRODUCTS)


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
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("M0041653", "DR007.IB", "S0059743", "S0059749", "S0059760"),
        "data_tables": ("fact_formal_yield_curve_daily", "fact_choice_macro_daily", "std_external_macro_daily"),
        "next_step": "7D 逆回购优先解析 Choice EMM00088132；legacy 仅保留历史观测，不做静默 carry-forward。",
    },
    {
        "key": "yield_curve_shape",
        "legacy_module": "M8",
        "label": "收益率曲线形态",
        "group": "曲线",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("S0059743", "S0059747", "S0059749"),
        "data_tables": ("fact_formal_yield_curve_daily",),
        "next_step": "观察口径曲线形态已上分析卡；缺 5Y/30Y 节点时次级利差诚实标 unavailable。",
    },
    {
        "key": "credit_spread_risk",
        "legacy_module": "M9",
        "label": "信用利差预警",
        "group": "信用",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("S0059652", "S0059747", "S0059760"),
        "data_tables": ("fact_formal_yield_curve_daily", "fact_choice_macro_daily"),
        "next_step": "观察口径信用利差风险已上分析卡；缺同期限 AA 腿或变动窗口时 degraded。",
    },
    {
        "key": "leading_indicator",
        "legacy_module": "M10",
        "label": "宏观领先指标",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("M0017126", "M0001385", "M5525763", "S0059743", "S0059749", "S0059670", "CA.BRENT"),
        "data_tables": ("fact_choice_macro_daily", "fact_formal_yield_curve_daily"),
        "next_step": "PMI(M0017126) 经 cycle_rotation/NBS/tushare 落库，不在 choice_macro_catalog；补齐历史窗口后提升 LEI 稳定度。",
    },
    {
        "key": "liquidity_stress",
        "legacy_module": "M11",
        "label": "流动性压力测试",
        "group": "压力测试",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("DR007.IB", "M0041813"),
        "data_tables": ("fact_formal_risk_tensor_daily",),
        "next_step": "观察口径流动性压力已上分析卡；桶字段缺失不计为 0 缺口。",
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
        "route_status": "wired",
        "frontend_status": "visible",
        # 实际消费：treasury_10y（曲线 enrich）、brent_oil、usdcny、us_treasury_10y（E1003238）。
        # VIX 无 catalog/落库序列；股债(VIX)相关腿继续诚实 unavailable。
        "data_aliases": ("CA.BRENT", "M0067855", "S0059749", "CA.US_GOV_10Y"),
        "data_tables": ("fact_formal_yield_curve_daily", "std_external_macro_daily", "fact_choice_macro_daily"),
        "next_step": "观察口径联动风险已上分析卡；美债 10Y 经 CA.US_GOV_10Y→E1003238 解析。VIX 系统源准入后可补齐股债相关腿。",
    },
    {
        "key": "rate_turning_point",
        "legacy_module": "M13",
        "label": "利率拐点判断",
        "group": "曲线",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("S0059743", "S0059749"),
        "data_tables": ("fact_formal_yield_curve_daily",),
        "next_step": "观察口径拐点信号已上分析卡；后续接入资金利率并沉淀拐点概率口径。",
    },
    {
        "key": "economic_cycle",
        "legacy_module": "M14",
        "label": "经济周期定位",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("M0017126", "M0000612", "M0001227", "M0001385", "M5525763"),
        "data_tables": ("fact_choice_macro_daily", "std_external_macro_daily"),
        "next_step": "增长/通胀宽表已接 PMI/CPI/PPI/M2/社融别名；补齐 vintage 前周期象限仅作 observation。",
    },
    {
        "key": "merrill_clock_cn",
        "legacy_module": "Merrill",
        "label": "美林时钟（中国版）",
        "group": "增长与通胀",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("M0017126", "M0000545", "M0000612", "M0001227", "M0001385", "M5525763"),
        "data_tables": ("fact_choice_macro_daily", "std_external_macro_daily"),
        "next_step": "观察口径美林时钟象限；补齐 PMI 新订单/发电量等增长代理历史后提升象限置信度。",
    },
    {
        "key": "cta_trend_cn",
        "legacy_module": "CTA",
        "label": "CTA 趋势跟踪",
        "group": "策略选择",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("sh000300", "sh000905", "CU0", "NH0100.NHF"),
        "data_tables": ("fact_choice_macro_daily", "fact_commodity_futures_daily"),
        "next_step": "观察口径 CTA 合成信号；黄金/原油腿缺系统别名时自动降级。",
    },
    {
        "key": "dcc_garch_cn",
        "legacy_module": "DCC",
        "label": "DCC-GARCH 相关",
        "group": "波动与相关",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("sh000300", "sh000905", "CU0", "NH0100.NHF"),
        "data_tables": ("fact_choice_macro_daily", "fact_commodity_futures_daily"),
        "next_step": "观察口径滚动相关预警；商品腿历史不足时标 insufficient_history。",
    },
    {
        "key": "risk_parity_cn",
        "legacy_module": "RP",
        "label": "风险平价影子",
        "group": "配置",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("sh000300", "sh000905", "CU0", "NH0100.NHF"),
        "data_tables": ("fact_choice_macro_daily", "fact_commodity_futures_daily"),
        "next_step": "影子权重仅观察；不执行再平衡，formal_use_allowed=false。",
    },
    {
        "key": "macro_portfolio_impact",
        "legacy_module": "M15",
        "label": "宏观情景组合影响",
        "group": "组合影响",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("S0059743", "S0059746", "S0059747", "S0059748", "S0059749"),
        "data_tables": ("fact_formal_yield_curve_daily", "fact_formal_bond_analytics_daily"),
        "next_step": "观察口径情景冲击已上分析卡；缺曲线节点时禁止默认收益率填洞。",
    },
    {
        "key": "decision_summary",
        "legacy_module": "M16",
        "label": "宏观决策摘要",
        "group": "决策摘要",
        "implementation_status": "library_ready",
        "route_status": "wired",
        "frontend_status": "visible",
        "data_aliases": ("DR007.IB", "S0059749", "sh000300", "M0067855"),
        "next_step": "细化聚合权重与证据引用，并沉淀为独立宏观决策端点。",
    },
)


def _gate_analysis_conclusion_on_refresh_receipt(
    conclusion: dict[str, object],
    warnings: list[str],
    refresh_receipt_health: (
        macro_toolkit_refresh_receipt_service.MacroToolkitRefreshReceiptHealth
    ),
) -> dict[str, object]:
    receipt_payload = refresh_receipt_health.as_payload()
    basis = conclusion.get("basis")
    normalized_basis = dict(basis) if isinstance(basis, dict) else {}
    normalized_basis["refresh_receipt"] = receipt_payload
    for warning in refresh_receipt_health.analysis_warnings():
        if warning not in warnings:
            warnings.append(warning)
    if refresh_receipt_health.ready:
        return {**conclusion, "basis": normalized_basis}
    return {
        "stance": "数据不足",
        "tone": "missing",
        "summary": "最近一次定时宏观刷新未通过完整性校验，当前指标仅作未验证观察证据。",
        "recommended_action": "先完成宏观数据刷新并通过回执校验，再形成方向性判断。",
        "basis": normalized_basis,
    }


def _macro_etf_strategy_snapshot_for_toolkit(
    *,
    duckdb_path: str | Path,
    as_of_date: str | None,
) -> dict[str, object]:
    try:
        envelope = macro_etf_strategy_service.macro_etf_strategy_envelope(
            as_of_date=as_of_date,
            duckdb_path=duckdb_path,
        )
        result = envelope.get("result")
        if isinstance(result, Mapping):
            return dict(result)
    except Exception as exc:  # pragma: no cover - defensive isolation for optional warmup surface
        failure_reason = exc.__class__.__name__
    else:
        failure_reason = "invalid_result_payload"
    return {
        "strategy_name": "macro_etf_rotation_observation",
        "boundary": "observation_only",
        "execution_enabled": False,
        "as_of_date": as_of_date,
        "dual_frequency": {
            "strategy_name": "a_share_dual_frequency_equity_observation",
            "boundary": "observation_only",
            "execution_enabled": False,
            "status": "degraded",
            "slow": {"status": "not_evaluated"},
            "fast": {"status": "not_evaluated"},
            "survival": {"status": "not_evaluated"},
            "pre_survival_target_total_weight": None,
            "final_target_total_weight": None,
            "warnings": [
                f"dual-frequency candidate unavailable in macro toolkit: {failure_reason}"
            ],
            "data_status": {
                "status": "degraded",
                "market_history_status": "not_evaluated",
                "slow_cap_status": "not_evaluated",
                "fast_status": "not_evaluated",
                "survival_status": "not_evaluated",
            },
        },
        "data_status": {
            "status": "degraded",
            "dual_frequency_status": "degraded",
        },
        "warnings": [f"macro ETF candidate unavailable in macro toolkit: {failure_reason}"],
        "provenance": {
            "integration_mode": "optional_read_only_candidate",
            "tables_used": [],
        },
    }


def _model_chain_artifacts_all_ok(chain_result: dict[str, object]) -> bool:
    steps = chain_result.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            return False
        for model in step.get("models") or []:
            if not isinstance(model, dict) or model.get("artifact_status") != "ok":
                return False
    return True


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


def _commodity_ordered_products(products: set[str]) -> list[str]:
    ordered = [product for product in _DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS if product in products]
    ordered.extend(sorted(product for product in products if product not in set(ordered)))
    return ordered


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
    ("CA.US_GOV_10Y", "US_GOVT", "10Y"),
)

_WIDE_SERIES_ALIASES = (
    ("hs300", "sh000300"),
    ("copper", "CU0"),
    ("usdcny", "M0067855"),
    ("fx_usdcny", "M0067855"),
    ("brent_oil", "CA.BRENT"),
    ("us_treasury_10y", "CA.US_GOV_10Y"),
    ("pmi", "M0017126"),
    ("cpi_yoy", "M0000612"),
    ("ppi_yoy", "M0001227"),
    ("m2_yoy", "M0001385"),
    ("social_financing_yoy", "M5525763"),
    ("industrial_yoy", "M0000545"),
    ("credit_spread_aaa_3y", "S0059670"),
    ("dr007", "DR007.IB"),
)

# 宽表 ffill 停止 carry 的最大陈旧天数（日历日）。月频用宽于 STALE_AFTER_DAYS
# 的窗口，避免把「自然发布滞后」误判为停更；日频允许跨周末。
_MONTHLY_WIDE_FIELDS = frozenset(
    {
        "pmi",
        "cpi_yoy",
        "ppi_yoy",
        "m2_yoy",
        "social_financing_yoy",
        "industrial_yoy",
    }
)
_WIDE_FFILL_MAX_STALE_DAYS = {
    "monthly": 65,
    "daily": 10,
}

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
            "aliases": ("S0059651", "S0059746"),
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
    "merrill_clock_cn": (
        {
            "field": "pmi",
            "label": "PMI",
            "aliases": ("M0017126",),
            "warning": "PMI_MISSING",
            "required": True,
        },
        {
            "field": "industrial_yoy",
            "label": "Industrial VA YoY",
            "aliases": ("M0000545",),
            "warning": "INDUSTRIAL_YOY_MISSING",
            "required": False,
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


_EQUITY_STRATEGY_PRICE_CONTEXT_UNSET = object()
_EQUITY_STRATEGY_PRICE_CONTEXT_UNAVAILABLE_WARNING = (
    "A股策略摘要不可用：未找到真实 choice_stock_daily_observation 价格上下文，已停止合成样本回退。"
)
_EQUITY_STRATEGY_NO_SUMMARIES_WARNING = (
    "A股策略摘要不可用：未返回真实策略摘要，已停止合成样本回退。"
)


def _latest_factor_snapshot_from_price_context(price_context: dict[str, object] | None) -> pd.DataFrame | None:
    if not isinstance(price_context, dict):
        return None
    financials = price_context.get("financials")
    if isinstance(financials, pd.DataFrame) and not financials.empty:
        return financials
    return None


def _equity_strategy_payload_data_status(
    summaries: list[dict[str, object]],
    *,
    deferred: bool = False,
    price_context_unavailable: bool = False,
) -> dict[str, object]:
    if deferred:
        return {"status": "deferred", "summary_count": 0}
    if price_context_unavailable or not summaries:
        return {
            "status": "unavailable",
            "reason": "price_context_unavailable" if price_context_unavailable else "no_strategy_summaries",
            "summary_count": len(summaries),
        }
    data_statuses = [_equity_strategy_summary_data_status(summary) for summary in summaries]
    if all(status == "complete" for status in data_statuses):
        status = "complete"
    elif any(status in {"complete", "degraded"} for status in data_statuses):
        status = "degraded"
    else:
        status = "unavailable"
    return {"status": status, "summary_count": len(summaries)}


def _equity_strategy_summary_data_status(summary: dict[str, object]) -> str:
    result = summary.get("result")
    if isinstance(result, Mapping):
        data_status = result.get("data_status")
        if isinstance(data_status, str) and data_status.strip():
            return data_status.strip()
    status = summary.get("status")
    return status.strip() if isinstance(status, str) and status.strip() else "unknown"


def _equity_strategy_payload_warnings(strategy_data_status: dict[str, object]) -> list[str]:
    if strategy_data_status.get("status") != "unavailable":
        return []
    if strategy_data_status.get("reason") == "price_context_unavailable":
        return [_EQUITY_STRATEGY_PRICE_CONTEXT_UNAVAILABLE_WARNING]
    return [_EQUITY_STRATEGY_NO_SUMMARIES_WARNING]


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


_MULTI_ASSET_PRICE_INPUTS = (
    {"field": "hs300", "alias": "sh000300", "label": "沪深300"},
    {"field": "csi500", "alias": "sh000905", "label": "中证500"},
    {"field": "copper", "alias": "CU0", "label": "铜"},
    {"field": "nanhua", "alias": "NH0100.NHF", "label": "南华商品"},
)


def _merrill_regime_from_payload(payload: Mapping[str, object] | None) -> str | None:
    if not payload:
        return None
    regime = payload.get("regime_label")
    if regime in {"复苏", "过热", "滞胀", "衰退"}:
        return str(regime)
    return None


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
        "shadow_evaluation": evaluate_crisis_commodity_shadow(frame, crisis_history),
    }


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


def _stale_warning_from_missing(missing_warning: str) -> str:
    if missing_warning.endswith("_MISSING"):
        return f"{missing_warning[: -len('_MISSING')]}_STALE"
    return f"{missing_warning}_STALE"


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
    derived_observation = _latest_wide_field_observation(field, wide_rows) if derived else None
    if derived:
        # 派生字段只消费宽表同源观测；禁止回退到腿 alias 的原始收益率冒充利差。
        value = derived_observation["value"] if derived_observation is not None else None
        available = value is not None
        if derived_observation is not None and derived_observation.get("source_date") is not None:
            latest_date = derived_observation["source_date"]
        else:
            latest_date = None
    else:
        value = latest.get("value") if isinstance(latest, dict) else None
        available = latest is not None
        latest_date = latest.get("date") if isinstance(latest, dict) else None
    cadence = str(requirement.get("cadence") or _input_cadence_for_field(field))
    freshness = assess_freshness(latest_date, report_date, cadence=cadence)
    stale = bool(
        available
        and freshness.tier in {FRESHNESS_TIER_STALE, FRESHNESS_TIER_EXPIRED}
    )
    provenance = (
        derived_observation.get("provenance")
        if derived_observation is not None
        else None
    )
    if not isinstance(provenance, dict):
        provenance = {}
    series_id = provenance.get("series_id")
    source = provenance.get("source") or provenance.get("vendor_name")
    # 派生字段已有宽表 provenance 时，禁止用 alias 腿 latest 回填 series_id/source
    #（value/date 已来自曲线派生观测，回填会造成身份错配）。
    if not (derived and provenance):
        if series_id is None and isinstance(latest, dict):
            series_id = latest.get("series_id")
        if source is None and isinstance(latest, dict):
            source = latest.get("vendor_name")
    elif series_id is None and provenance.get("transform") is not None:
        # 曲线/transform 派生观测：无独立 series_id 时用明确身份，避免空串歧义。
        series_id = "curve_derived"
        if source is None:
            source = "curve_derived"
    item: dict[str, object] = {
        "field": field,
        "label": str(requirement["label"]),
        "aliases": list(aliases),
        "warning": str(requirement["warning"]),
        "required": bool(requirement.get("required", True)),
        "available": available,
        "stale": stale,
        "stale_days": freshness.age_days if stale else None,
        "freshness_tier": freshness.tier if available else None,
        "cadence": cadence,
        "row_count": int(check.get("row_count") or 0),
        "latest_date": latest_date,
        "series_id": series_id,
        "source": source,
        "value": value,
    }
    if derived and provenance:
        if provenance.get("unit") is not None:
            item["unit"] = provenance["unit"]
        if provenance.get("unit_status") is not None:
            item["unit_status"] = provenance["unit_status"]
        if provenance.get("transform") is not None:
            item["transform"] = provenance["transform"]
        legs = provenance.get("legs")
        if isinstance(legs, dict):
            item["legs"] = {
                leg_name: _serialize_provenance_leg(leg_meta)
                for leg_name, leg_meta in legs.items()
            }
        # 未冻结单位仅作 observation 披露，绝不解除 formal。
        item["formal_use_allowed"] = False
        item["observation_only"] = True
    return item


def _input_cadence_for_field(field: str) -> str:
    if field in _MONTHLY_WIDE_FIELDS or field.endswith("_yoy") or field == "pmi":
        return "monthly"
    return "daily"


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
    observation = _latest_wide_field_observation(field, wide_rows)
    if observation is None:
        return None
    value = observation.get("value")
    return float(value) if value is not None else None


def _latest_wide_field_observation(
    field: str,
    wide_rows: list[dict[str, object]],
) -> dict[str, object] | None:
    """取宽表中该字段最新非空观测，并附带同源 source_date / provenance。"""
    for row in wide_rows:
        value = _float_or_none(row.get(field))
        if value is None:
            continue
        source_date = row.get(f"{field}_source_date")
        if isinstance(source_date, date):
            source_date_text = source_date.isoformat()
        elif source_date is not None:
            source_date_text = str(source_date)[:10]
        else:
            trade = row.get("trade_date") or row.get("biz_date")
            source_date_text = trade.isoformat() if isinstance(trade, date) else (
                str(trade)[:10] if trade is not None else None
            )
        row_provenance = row.get("_provenance")
        field_provenance = None
        if isinstance(row_provenance, dict):
            candidate = row_provenance.get(field)
            if isinstance(candidate, dict):
                field_provenance = dict(candidate)
                prov_date = field_provenance.get("source_date")
                if isinstance(prov_date, date):
                    field_provenance["source_date"] = prov_date
                    source_date_text = prov_date.isoformat()
                elif prov_date is not None:
                    source_date_text = str(prov_date)[:10]
        return {
            "value": value,
            "source_date": source_date_text,
            "provenance": field_provenance or {},
        }
    return None


def _serialize_provenance_leg(leg_meta: object) -> dict[str, object]:
    if not isinstance(leg_meta, dict):
        return {}
    serialized = dict(leg_meta)
    leg_date = serialized.get("source_date")
    if isinstance(leg_date, date):
        serialized["source_date"] = leg_date.isoformat()
    elif leg_date is not None:
        serialized["source_date"] = str(leg_date)[:10]
    return serialized


def _load_macro_capability_context(
    duckdb_path: str | Path,
    report_date: date,
) -> tuple[list[dict[str, object]], dict[str, object] | None, list[dict[str, object]]]:
    return macro_toolkit_service.load_macro_capability_context(duckdb_path, report_date)


def _load_macro_wide_rows(
    duckdb_path: str | Path,
    report_date: date,
    curve_rows: list[dict[str, object]],
    *,
    frames_by_alias: dict[str, pd.DataFrame] | None = None,
) -> list[dict[str, object]]:
    wide_by_date: dict[date, dict[str, float]] = {report_date: {}}
    source_dates_by_date: dict[date, dict[str, date]] = {}
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
            source_dates_by_date.setdefault(sample_date, {})[field] = sample_date

    for row in curve_rows:
        row_date = _parse_report_date(str(row.get("biz_date") or ""))
        if row_date is not None and row_date <= report_date:
            wide_by_date.setdefault(row_date, {})

    # ffill with per-field stale cap: stop carrying once the gap from the
    # original observation exceeds the cadence limit (monthly ~65d / daily ~10d).
    last_seen: dict[str, float] = {}
    last_seen_date: dict[str, date] = {}
    for sample_date in sorted(wide_by_date):
        current = wide_by_date[sample_date]
        fresh_fields = {field for field in fields if field in current}
        for field in fields:
            if field not in current and field in last_seen:
                cadence = "monthly" if field in _MONTHLY_WIDE_FIELDS else "daily"
                max_stale = _WIDE_FFILL_MAX_STALE_DAYS[cadence]
                if (sample_date - last_seen_date[field]).days <= max_stale:
                    current[field] = last_seen[field]
                    source_dates_by_date.setdefault(sample_date, {})[field] = last_seen_date[field]
        for field in fresh_fields:
            value = current.get(field)
            if value is not None:
                last_seen[field] = value
                last_seen_date[field] = sample_date

    curves_by_date = build_curve_history(curve_rows, report_date=report_date)
    curve_provenance_by_date: dict[date, dict[str, dict[str, object]]] = {}
    enrich_wide_with_curve_market_fields(
        wide_by_date,
        curves_by_date,
        provenance_by_date=curve_provenance_by_date,
    )
    wide_rows = sort_wide_rows_for_macro(wide_by_date, report_date=report_date)
    for row in wide_rows:
        row_date = row["trade_date"]
        for field, source_date in source_dates_by_date.get(row_date, {}).items():
            row[f"{field}_source_date"] = source_date
        # 曲线 enrich 覆盖派生值时，原子替换 *_source_date 与 page-local _provenance。
        derived_provenance = curve_provenance_by_date.get(row_date)
        if derived_provenance:
            row_provenance = dict(row.get("_provenance") or {})
            for field, meta in derived_provenance.items():
                source_date = meta.get("source_date")
                if isinstance(source_date, date):
                    row[f"{field}_source_date"] = source_date
                row_provenance[field] = dict(meta)
            row["_provenance"] = row_provenance
    return wide_rows


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


_OBSERVATION_KEYS_CONFIG_PATH = _REPO_ROOT / "config" / "macro_decision_observation_keys.json"


def _load_decision_summary_observation_keys(path: Path | None = None) -> frozenset[str]:
    config_path = path or _OBSERVATION_KEYS_CONFIG_PATH
    if not config_path.is_file():
        raise FileNotFoundError(
            "Decision summary observation keys config missing: "
            f"{config_path}. Ship config/macro_decision_observation_keys.json with deploy packages."
        )
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in decision summary observation keys config: {config_path}"
        ) from exc
    keys = payload.get("observation_keys")
    if not isinstance(keys, list) or not keys or not all(isinstance(key, str) and key for key in keys):
        raise ValueError(f"Invalid observation_keys in {config_path}")
    return frozenset(keys)


@lru_cache(maxsize=1)
def _decision_summary_observation_keys() -> frozenset[str]:
    """Lazy-load observation keys; import must not require the config file."""
    return _load_decision_summary_observation_keys()


def _decision_summary_card(
    definition: dict[str, object],
    cards: list[dict[str, object]],
    report_date: date,
) -> dict[str, object]:
    usable_cards = [card for card in cards if card["status"] in {"complete", "degraded"}]
    # observation_only 卡（美林时钟/CTA/DCC/风险平价）计入可用分母，
    # 但不参与驱动久期/信用行动建议的方向投票。
    observation_keys = _decision_summary_observation_keys()
    voting_cards = [
        card for card in usable_cards if str(card["key"]) not in observation_keys
    ]
    positive_count = sum(1 for card in voting_cards if card["tone"] == "positive")
    negative_count = sum(1 for card in voting_cards if card["tone"] == "negative")
    missing_count = sum(1 for card in cards if card["status"] == "unavailable")
    total_count = len(cards)
    if not usable_cards:
        tone = "missing"
        headline = "宏观模块均不可用，无法给出方向性判断。"
    elif negative_count > positive_count:
        tone = "negative"
        headline = "宏观信号偏谨慎，优先控制久期和信用敞口。"
    elif positive_count > negative_count:
        tone = "positive"
        headline = "宏观信号偏支持，组合可保留适度久期与高等级信用。"
    else:
        tone = "neutral"
        headline = "宏观信号分化，维持中性观察。"
    if not usable_cards:
        status = "unavailable"
    elif len(usable_cards) == total_count and missing_count == 0:
        status = "complete"
    else:
        status = "degraded"
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
        "score": max(0.0, min(100.0, score)) if usable_cards else None,
        "headline": headline,
        "primary_metric": _metric("可用模块", len(usable_cards), f"/{total_count}"),
        "evidence": evidence,
        "warnings": ["宏观模块结果全部不可用"]
        if status == "unavailable"
        else ["部分模块数据降级或不可用"]
        if status == "degraded"
        else [],
        "result": {
            "report_date": report_date.isoformat(),
            "data_status": status,
            "formal_use_allowed": False,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "observation_excluded_count": len(usable_cards) - len(voting_cards),
            "missing_count": missing_count,
            "usable_count": len(usable_cards),
            "headline": headline,
        },
    }


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


_INDICATOR_RECENT_POINT_LIMIT = 20


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
            "recent_points": [],
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
    recent_points = [
        {"date": str(row["date"])[:10], "value": round(float(row["value"]), 4)}
        for _, row in ordered.tail(_INDICATOR_RECENT_POINT_LIMIT).iterrows()
    ]
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
        "recent_points": recent_points,
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
