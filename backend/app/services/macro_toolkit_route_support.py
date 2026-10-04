"""Read collaborators and HTTP support for the macro toolkit.

Owns data reads and analytical orchestration shared by the read service and
routes. This module must never import the route module.
"""
from __future__ import annotations

import calendar
import json
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict, cast

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
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)
from backend.app.services.macro_toolkit_analysis_service import (
    _a_share_stampede_risk_card,
    _capability_result_card,
    _credit_card,
    _crisis_commodity_candidate_admission,
    _crisis_commodity_candidate_approval_pack,
    _crisis_commodity_candidate_decision,
    _crisis_commodity_candidate_summary,
    _crisis_commodity_shadow_impact,
    _crisis_score_card,
    _float_or_none,
    _liquidity_card,
    _metric,
    _risk_appetite_card,
    _script_output_card,
    _unavailable_capability_result,
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
from backend.app.services.macro_toolkit_read_service import MacroToolkitResultMetaOverrides

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


def _gate_primary_signal_on_refresh_receipt(
    primary_signal: Mapping[str, object] | None,
    refresh_receipt_health: (
        macro_toolkit_refresh_receipt_service.MacroToolkitRefreshReceiptHealth
    ),
) -> dict[str, object]:
    normalized = dict(primary_signal or {})
    if refresh_receipt_health.ready:
        return normalized
    reason_code = {
        "missing": "refresh_receipt_missing",
        "invalid": "refresh_receipt_invalid",
        "blocked": "refresh_receipt_blocked",
    }.get(refresh_receipt_health.status, "refresh_receipt_unverified")
    normalized["key"] = None
    normalized["selection_status"] = "blocked"
    normalized["reason_code"] = reason_code
    normalized["refresh_receipt_status"] = refresh_receipt_health.status
    return normalized


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
            if model.get("id") == "backtest":
                backtest_context = model.get("backtest_context")
                if (
                    not isinstance(backtest_context, dict)
                    or backtest_context.get("quality_flag") != "ok"
                ):
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
    expected_user_id: str | None = None,
) -> dict[str, object]:
    return macro_toolkit_service.choice_stock_refresh_status(
        governance_path,
        run_id=run_id,
        expected_user_id=expected_user_id,
    )


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
    expected_user_id: str | None = None,
) -> dict[str, object]:
    return macro_toolkit_service.choice_stock_refresh_overview(
        duckdb_path,
        governance_path,
        permission=permission,
        reference_date=reference_date,
        expected_user_id=expected_user_id,
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
    return score_frame.dropna(subset=["crisis_score"])


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


def _capability_freshness_reference(
    latest_date: object,
    report_date: date,
    *,
    cadence: str,
) -> tuple[object, str | None, str | None]:
    """Return the date that truthfully represents freshness for this input."""
    if cadence.strip().lower() != "monthly":
        return latest_date, None, None

    observation_date = _coerce_frame_date(latest_date)
    if observation_date is None:
        return latest_date, None, "unknown"

    # Only a first-of-month key is known to encode a statistical period.
    # Some legacy/vendor rows carry an actual release or observation day;
    # moving those dates to month-end would manufacture look-ahead evidence.
    if observation_date.day != 1:
        return observation_date, observation_date.isoformat(), "observation_date"

    # A later observation month is genuine look-ahead evidence. Keep its
    # original date so the freshness assessor reports the real negative age.
    if (observation_date.year, observation_date.month) > (
        report_date.year,
        report_date.month,
    ):
        return observation_date, observation_date.isoformat(), "observation_date"

    period_end = observation_date.replace(
        day=calendar.monthrange(observation_date.year, observation_date.month)[1]
    )
    return period_end, period_end.isoformat(), "observation_period_end"


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
    freshness_date, freshness_reference_date, freshness_basis = (
        _capability_freshness_reference(
            latest_date,
            report_date,
            cadence=cadence,
        )
    )
    freshness = assess_freshness(freshness_date, report_date, cadence=cadence)
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
    if cadence.strip().lower() == "monthly":
        item["freshness_reference_date"] = freshness_reference_date
        item["freshness_basis"] = freshness_basis
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
    dv01 = _float_or_none(row.get("portfolio_dv01"))
    bond_count = _float_or_none(row.get("bond_count"))
    if dv01 is not None:
        proxy_rows.append(
            {
                "book_id": "portfolio",
                # risk_tensor 的 issuer_top5_weight 是发行人市值 Top5 集中度（利率债组合
                # 常态 0.6-1.0），不是单账簿 DV01 份额，填入会恒触发 CRITICAL 集中度告警。
                # fail-closed 置 None：集中度腿不参与压力评分，待真实账簿级 DV01 数据接入后再启用。
                "share_of_abs_dv01": None,
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


_M15_REQUIRED_GOV_CURVE_TENORS = ("1Y", "3Y", "5Y", "7Y", "10Y")


def _current_gov_curve_snapshot(
    curve_rows: list[dict[str, object]],
    report_date: date,
) -> tuple[dict[str, float], dict[str, object]]:
    """Select one atomic CN_GOVT snapshot for the M15 scenario engine."""
    curves_by_date = build_curve_history(curve_rows, report_date=report_date)
    government_dates = [
        sample_date
        for sample_date in sorted(curves_by_date.keys(), reverse=True)
        if curves_by_date.get(sample_date, {}).get("CN_GOVT")
    ]
    base_evidence: dict[str, object] = {
        "requested_report_date": report_date.isoformat(),
        "curve_date": None,
        "fallback_mode": "none_available",
        "stale_days": None,
        "missing_tenors": list(_M15_REQUIRED_GOV_CURVE_TENORS),
    }
    if not government_dates:
        return {}, base_evidence

    latest_curve_date = government_dates[0]
    complete_dates = [
        sample_date
        for sample_date in government_dates
        if all(
            tenor in curves_by_date[sample_date]["CN_GOVT"]
            for tenor in _M15_REQUIRED_GOV_CURVE_TENORS
        )
    ]
    curve_date = complete_dates[0] if complete_dates else latest_curve_date
    government_curve = curves_by_date[curve_date]["CN_GOVT"]
    selected_curve = {tenor: float(rate) for tenor, rate in government_curve.items()}
    missing_tenors = [
        tenor
        for tenor in _M15_REQUIRED_GOV_CURVE_TENORS
        if tenor not in government_curve
    ]
    fallback_mode = "none"
    if not complete_dates:
        fallback_mode = "none_available"
    elif curve_date != latest_curve_date:
        fallback_mode = "latest_complete_snapshot"
    return selected_curve, {
        **base_evidence,
        "curve_date": curve_date.isoformat(),
        "fallback_mode": fallback_mode,
        "stale_days": (report_date - curve_date).days,
        "missing_tenors": missing_tenors,
    }


def _current_gov_curve(
    curve_rows: list[dict[str, object]],
    report_date: date,
) -> dict[str, float]:
    """Compatibility view for callers that only need the selected curve."""
    selected_curve, _ = _current_gov_curve_snapshot(curve_rows, report_date)
    return selected_curve


def _with_macro_portfolio_curve_snapshot_evidence(
    result: dict[str, object],
    evidence: Mapping[str, object],
) -> dict[str, object]:
    warnings = [str(item) for item in cast(Iterable[object], result.get("warnings", [])) if item]
    data_status = str(result.get("data_status") or "unavailable")
    if evidence.get("fallback_mode") == "latest_complete_snapshot":
        if "CURVE_DATE_FALLBACK" not in warnings:
            warnings.append("CURVE_DATE_FALLBACK")
        if data_status == "complete":
            data_status = "degraded"
    return {
        **result,
        **evidence,
        "data_status": data_status,
        "warnings": warnings,
    }


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
        "label": "SHIBOR 3M（期限报价参考）" if str(latest["series_id"]) == "NCD.SHIBOR.3M" else config["label"],
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


_ANALYSIS_DIRECTIONAL_SIGNAL_KEYS = frozenset(
    {
        "liquidity",
        "risk_appetite",
        "credit",
    }
)


def _analysis_conclusion(
    signal_cards: list[dict[str, object]],
    coverage: dict[str, object],
) -> dict[str, object]:
    directional_cards = {
        str(card["key"]): {"key": str(card["key"]), "tone": str(card["tone"])}
        for card in signal_cards
        if card.get("key") in _ANALYSIS_DIRECTIONAL_SIGNAL_KEYS
        and card.get("tone") in {"positive", "negative", "neutral"}
    }
    missing_keys = sorted(_ANALYSIS_DIRECTIONAL_SIGNAL_KEYS - directional_cards.keys())
    basis = {
        "source": "core_signal_cards",
        "signal_cards": list(directional_cards.values()),
        "directional_coverage": {
            "expected_count": len(_ANALYSIS_DIRECTIONAL_SIGNAL_KEYS),
            "valid_count": len(directional_cards),
            "missing_keys": missing_keys,
            "status": "insufficient" if missing_keys else "complete",
        },
    }
    hit_rate = float(coverage["hit_rate"])
    if hit_rate < 0.6:
        return {
            "stance": "数据不足",
            "tone": "missing",
            "summary": "核心指标命中不足，当前页面只展示可用证据，不形成完整方向判断。",
            "recommended_action": "先补齐缺失的 Choice/Tushare 序列，再运行信号脚本。",
            "basis": basis,
        }

    # Indicator hit rate does not prove that all directional inputs are available.
    if missing_keys:
        return {
            "stance": "暂不判断",
            "tone": "missing",
            "summary": (
                f"方向信号有效 {len(directional_cards)}/{len(_ANALYSIS_DIRECTIONAL_SIGNAL_KEYS)} 项，"
                "流动性、风险偏好或信用利差证据尚未齐备，当前只展示可用证据，暂不形成方向判断。"
            ),
            "recommended_action": "先补齐缺失方向信号的输入，再复核市场方向。",
            "basis": basis,
        }

    tones = [card["tone"] for card in directional_cards.values()]
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
    return {
        "stance": stance,
        "tone": tone,
        "summary": summary,
        "recommended_action": action,
        "basis": basis,
    }


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


_HEALTHY_META_STATES = frozenset(
    {
        "ok",
        "ready",
        "complete",
        "completed",
        "queued",
        "dry_run",
        "visible",
        "wired",
        "library_ready",
        "integrated",
        "current",
        "present",
        "aligned",
    }
)
_DEGRADED_META_STATES = frozenset(
    {
        "warning",
        "degraded",
        "partial",
        "stale",
        "vendor_stale",
        "lagging",
        "future",
        "mixed",
        "invalid_date",
        "unknown",
    }
)
_UNAVAILABLE_META_STATES = frozenset(
    {
        "error",
        "failed",
        "failure",
        "invalid",
        "missing",
        "unavailable",
        "vendor_unavailable",
        "missing_database",
        "unreadable_database",
        "missing_table",
        "empty_table",
        "query_failed",
        "no_data",
        "not_ready",
        "not_configured",
    }
)
_IGNORED_META_STATES = frozenset({"", "deferred", "none", "not_evaluated", "off"})


class _MacroResultMetaFlags(TypedDict):
    has_quality_warning: bool
    has_degraded: bool
    has_unavailable: bool
    has_vendor_stale: bool
    has_vendor_unavailable: bool
    has_latest_snapshot: bool
    tables_used: list[str]


def _aggregate_macro_result_meta_overrides(result: Mapping[str, object]) -> MacroToolkitResultMetaOverrides:
    flags: _MacroResultMetaFlags = {
        "has_quality_warning": False,
        "has_degraded": False,
        "has_unavailable": False,
        "has_vendor_stale": False,
        "has_vendor_unavailable": False,
        "has_latest_snapshot": False,
        "tables_used": [],
    }
    _collect_macro_result_meta_flags(result, flags)
    quality_flag: QualityFlag = (
        "warning"
        if flags["has_quality_warning"] or flags["has_degraded"] or flags["has_unavailable"]
        else "ok"
    )
    vendor_status: VendorStatus = (
        "vendor_unavailable"
        if flags["has_vendor_unavailable"]
        else "vendor_stale"
        if flags["has_vendor_stale"]
        else "ok"
    )
    return {
        "quality_flag": quality_flag,
        "vendor_status": vendor_status,
        "fallback_mode": "latest_snapshot" if flags["has_latest_snapshot"] else "none",
        "tables_used": _unique_texts(flags["tables_used"]),
    }


def _collect_macro_result_meta_flags(value: object, flags: _MacroResultMetaFlags) -> None:
    if isinstance(value, Mapping):
        _append_tables_used(flags["tables_used"], value.get("tables_used"))
        provenance = value.get("provenance")
        if isinstance(provenance, Mapping):
            _append_tables_used(flags["tables_used"], provenance.get("tables_used"))

        _record_macro_meta_state(value.get("quality_flag"), flags, quality_only=True)
        _record_macro_vendor_state(value.get("vendor_status"), flags)
        _record_macro_fallback_mode(value.get("fallback_mode"), flags)
        _record_macro_meta_state(value.get("status"), flags)
        _record_macro_meta_state(value.get("quality"), flags)

        data_status = value.get("data_status")
        if isinstance(data_status, Mapping):
            _record_macro_meta_state(data_status.get("status"), flags)
            for nested_key in (
                "dual_frequency_status",
                "market_history_status",
                "slow_cap_status",
                "fast_status",
                "survival_status",
            ):
                _record_macro_meta_state(data_status.get(nested_key), flags)
        else:
            _record_macro_meta_state(data_status, flags)
        _record_macro_meta_state(value.get("freshness_status"), flags)

        if "warnings" in value and isinstance(value.get("warnings"), list) and value.get("warnings"):
            flags["has_quality_warning"] = True

        for nested in value.values():
            _collect_macro_result_meta_flags(nested, flags)
        return

    if isinstance(value, list):
        for item in value:
            _collect_macro_result_meta_flags(item, flags)


def _append_tables_used(target: list[str], value: object) -> None:
    if isinstance(value, (list, tuple, set)):
        for table in value:
            table_name = str(table or "").strip()
            if table_name:
                target.append(table_name)


def _record_macro_vendor_state(value: object, flags: _MacroResultMetaFlags) -> None:
    normalized = str(value or "").strip()
    if normalized == "vendor_unavailable":
        flags["has_vendor_unavailable"] = True
    elif normalized == "vendor_stale":
        flags["has_vendor_stale"] = True


def _record_macro_fallback_mode(value: object, flags: _MacroResultMetaFlags) -> None:
    if str(value or "").strip() == "latest_snapshot":
        flags["has_latest_snapshot"] = True


def _record_macro_meta_state(
    value: object,
    flags: _MacroResultMetaFlags,
    *,
    quality_only: bool = False,
) -> None:
    normalized = str(value or "").strip()
    if normalized in _IGNORED_META_STATES or normalized in _HEALTHY_META_STATES:
        return
    if normalized in _UNAVAILABLE_META_STATES:
        flags["has_unavailable"] = True
        return
    if normalized in _DEGRADED_META_STATES:
        if quality_only:
            flags["has_quality_warning"] = True
        else:
            flags["has_degraded"] = True
        return
    if quality_only:
        flags["has_quality_warning"] = True


def _envelope(
    result_kind: str,
    result: dict[str, object],
    *,
    quality_flag: str | None = None,
    vendor_status: str | None = None,
    fallback_mode: str | None = None,
    tables_used: list[str] | None = None,
    as_of_date: str | None = None,
) -> dict[str, object]:
    generated_at = datetime.now(UTC).isoformat()
    resolved_tables_used = list(tables_used) if tables_used is not None else [
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "fx_daily_mid",
        "fact_formal_yield_curve_daily",
        "std_external_macro_daily",
        "fact_commodity_futures_daily",
        "fact_cffex_member_rank_daily",
        "vw_cffex_member_rank_daily",
    ]
    if tables_used is None:
        if "capability_results" in result:
            resolved_tables_used.extend(
                [
                    "fact_formal_risk_tensor_daily",
                    "fact_formal_bond_analytics_daily",
                ]
            )
        if _strategy_summaries_use_choice_stock(result):
            resolved_tables_used.append("choice_stock_daily_observation")
        if _strategy_summaries_use_stock_factor_snapshot(result):
            resolved_tables_used.append("choice_stock_factor_snapshot")
        shadow_report = result.get("shadow_portfolio_report")
        if isinstance(shadow_report, dict):
            report_tables = shadow_report.get("tables_used")
            if isinstance(report_tables, list):
                resolved_tables_used.extend(str(table) for table in report_tables)
        if "choice_stock_refresh" in result:
            resolved_tables_used.extend(["choice_stock_daily_observation", "choice_stock_factor_snapshot"])
        a_share_risk = result.get("a_share_risk")
        if isinstance(a_share_risk, dict):
            risk_tables = a_share_risk.get("tables_used")
            if isinstance(risk_tables, list):
                resolved_tables_used.extend(str(table) for table in risk_tables)
    return build_result_envelope(
        basis="analytical",
        trace_id=f"macro-toolkit-{uuid.uuid4().hex[:12]}",
        result_kind=result_kind,
        cache_version="none",
        source_version="macro_toolkit_registry",
        rule_version="rv_macro_toolkit_ui_v1",
        result_payload=result,
        quality_flag=cast(QualityFlag, quality_flag or "ok"),
        vendor_version="choice+tushare",
        vendor_status=cast(VendorStatus, vendor_status or "ok"),
        fallback_mode=cast(FallbackMode, fallback_mode or "none"),
        tables_used=_unique_texts(resolved_tables_used),
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

def _commodity_futures_status(duckdb_path: str | Path) -> dict[str, object]:
    return macro_toolkit_service.commodity_futures_status(duckdb_path)

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
    definition: Mapping[str, object],
    duckdb_path: str | Path,
    *,
    source_check_cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    aliases = tuple(str(alias) for alias in cast(Sequence[str], definition["data_aliases"]))
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
        "data_tables": [str(table) for table in cast(Sequence[str], definition.get("data_tables", ()))],
        "evidence": [
            {
                "alias": check["alias"],
                "row_count": check["row_count"],
                "latest_date": cast(dict[str, object], check["latest"])["date"] if check["latest"] else None,
                "series_id": cast(dict[str, object], check["latest"])["series_id"] if check["latest"] else None,
            }
            for check in checks
        ],
        "next_step": "已在本页输出结构化结果；下一步沉淀为正式宏观端点和页面契约。",
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
            _crisis_score_card_without_analysis_date(cast(dict[str, object], item), duckdb_path, crisis_report_date)
            if item["key"] == "crisis_score_cn"
            else _unavailable_capability_result(cast(dict[str, object], item), "缺少可用分析日期")
            for item in _CAPABILITY_DEFINITIONS
        ]

    curve_rows, risk_tensor, positions = _load_macro_capability_context(
        duckdb_path,
        parsed_report_date,
    )
    report_date_frames_by_alias = load_series_by_aliases(
        tuple(
            dict.fromkeys(
                [
                    *(alias for _, alias in _WIDE_SERIES_ALIASES),
                    *(
                        str(alias)
                        for requirements in _CAPABILITY_INPUT_REQUIREMENTS.values()
                        for requirement in requirements
                        for alias in cast(Sequence[str], requirement.get("aliases", ()))
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
    proxy_rows, bucket_rows, total_assets = _risk_tensor_to_liquidity_inputs(risk_tensor)
    portfolio_profile = build_bond_portfolio_profile(positions, parsed_report_date)
    current_curve, current_curve_snapshot_evidence = _current_gov_curve_snapshot(
        curve_rows,
        parsed_report_date,
    )

    merrill_raw = _run_capability(
        "merrill_clock_cn",
        lambda: compute_merrill_clock_payload(wide_rows, report_date=parsed_report_date),
    )
    risk_parity_clock_phase = _merrill_regime_from_payload(merrill_raw)
    multi_asset_series_cache: dict[str, list[tuple[date, float]]] | None = None

    def _shared_multi_asset_series() -> dict[str, list[tuple[date, float]]]:
        nonlocal multi_asset_series_cache
        if multi_asset_series_cache is None:
            multi_asset_series_cache = _load_multi_asset_price_series(
                duckdb_path,
                parsed_report_date,
            )
        return multi_asset_series_cache

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
        "merrill_clock_cn": merrill_raw,
        "cta_trend_cn": _run_capability(
            "cta_trend_cn",
            lambda: _compute_multi_asset_observation_capability(
                "cta_trend_cn",
                duckdb_path,
                parsed_report_date,
                series_data=_shared_multi_asset_series(),
            ),
        ),
        "dcc_garch_cn": _run_capability(
            "dcc_garch_cn",
            lambda: _compute_multi_asset_observation_capability(
                "dcc_garch_cn",
                duckdb_path,
                parsed_report_date,
                series_data=_shared_multi_asset_series(),
            ),
        ),
        "risk_parity_cn": _run_capability(
            "risk_parity_cn",
            lambda: _compute_multi_asset_observation_capability(
                "risk_parity_cn",
                duckdb_path,
                parsed_report_date,
                clock_phase=risk_parity_clock_phase,
                series_data=_shared_multi_asset_series(),
            ),
        ),
        "macro_portfolio_impact": _run_capability(
            "macro_portfolio_impact",
            lambda: _with_macro_portfolio_curve_snapshot_evidence(
                compute_macro_portfolio_impact(
                    portfolio_profile,
                    current_curve,
                    parsed_report_date,
                ),
                current_curve_snapshot_evidence,
            ),
        ),
    }
    input_evidence_source_check_cache: dict[str, dict[str, object]] = {}
    _source_checks_for_aliases(
        (
            str(alias)
            for requirements in _CAPABILITY_INPUT_REQUIREMENTS.values()
            for requirement in requirements
            for alias in cast(Sequence[str], requirement.get("aliases", ()))
        ),
        duckdb_path,
        source_check_cache=input_evidence_source_check_cache,
        end=parsed_report_date.isoformat(),
        frames_by_alias=report_date_frames_by_alias,
    )
    for key in ("monetary_policy_stance", "leading_indicator", "economic_cycle", "merrill_clock_cn"):
        raw_results[key] = _with_capability_input_evidence(
            key,
            raw_results[key],
            duckdb_path=duckdb_path,
            report_date=parsed_report_date,
            wide_rows=wide_rows,
            source_check_cache=input_evidence_source_check_cache,
            source_frames_by_alias=report_date_frames_by_alias,
        )

    return _assemble_capability_cards(raw_results, parsed_report_date)

def _assemble_capability_cards(
    raw_results: dict[str, dict[str, object]],
    report_date: date,
) -> list[dict[str, object]]:
    """Build capability cards; the decision summary always aggregates every
    non-decision card regardless of its position in the definition tuple."""
    non_decision_cards = {
        str(definition["key"]): _capability_result_card(cast(dict[str, object], definition), raw_results.get(str(definition["key"])))
        for definition in _CAPABILITY_DEFINITIONS
        if definition["key"] != "decision_summary"
    }
    cards: list[dict[str, object]] = []
    for definition in _CAPABILITY_DEFINITIONS:
        if definition["key"] == "decision_summary":
            cards.append(
                _decision_summary_card(cast(dict[str, object], definition), list(non_decision_cards.values()), report_date)
            )
            continue
        cards.append(non_decision_cards[str(definition["key"])])
    return cards

def _equity_strategy_summaries_with_context(
    duckdb_path: str | Path | None = None,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    try:
        price_context = _load_equity_strategy_price_context(duckdb_path)
        return _equity_strategy_summaries(duckdb_path, price_context=price_context), price_context
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return [_unavailable_equity_strategy_summary(exc)], None

def _equity_strategy_summaries(
    duckdb_path: str | Path | None = None,
    *,
    price_context: object = _EQUITY_STRATEGY_PRICE_CONTEXT_UNSET,
) -> list[dict[str, object]]:
    try:
        if price_context is _EQUITY_STRATEGY_PRICE_CONTEXT_UNSET:
            price_context = _load_equity_strategy_price_context(duckdb_path)
        if price_context is None:
            return []
        return _real_equity_strategy_summaries(cast(dict[str, object], price_context))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return [_unavailable_equity_strategy_summary(exc)]

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
    tables_used = [str(item) for item in cast(Iterable[object], context.get("tables_used", []))]
    payload["tables_used"] = _unique_texts([*payload.get("tables_used", []), *tables_used])
    if context.get("warnings"):
        payload["warnings"] = _unique_texts([*payload.get("warnings", []), *cast(Iterable[object], context["warnings"])])
        if payload.get("status") == "complete":
            payload["status"] = "degraded"
    return payload

def _load_a_share_stampede_risk_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    return macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)

def _load_equity_strategy_price_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    return macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)

def _load_multi_asset_price_series(
    duckdb_path: str | Path,
    report_date: date,
    *,
    lookback_days: int = 800,
) -> dict[str, list[tuple[date, float]]]:
    start = report_date - timedelta(days=lookback_days)
    aliases = tuple(str(item["alias"]) for item in _MULTI_ASSET_PRICE_INPUTS)
    frames_by_alias = load_series_by_aliases(
        aliases,
        start=start.isoformat(),
        end=report_date.isoformat(),
        duckdb_path=duckdb_path,
    )
    # 缺数据的腿保留为空列表：库层 _normalize_prices 会据此产出
    # {FIELD}_MISSING 警告并把状态降级，而不是静默丢腿。
    return {
        str(item["field"]): _frame_to_crisis_points(frames_by_alias[str(item["alias"])])
        for item in _MULTI_ASSET_PRICE_INPUTS
    }

def _compute_multi_asset_observation_capability(
    key: str,
    duckdb_path: str | Path,
    report_date: date,
    *,
    clock_phase: str | None = None,
    series_data: dict[str, list[tuple[date, float]]] | None = None,
) -> dict[str, object]:
    resolved_series = (
        series_data
        if series_data is not None
        else _load_multi_asset_price_series(duckdb_path, report_date)
    )
    if key == "cta_trend_cn":
        return compute_cta_trend_payload(resolved_series, report_date=report_date)
    if key == "dcc_garch_cn":
        return compute_dcc_garch_payload(resolved_series, report_date=report_date)
    if key == "risk_parity_cn":
        return compute_risk_parity_payload(
            resolved_series,
            report_date=report_date,
            clock_phase=clock_phase,
        )
    raise ValueError(f"unsupported multi-asset observation capability: {key}")

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

    result = compute_crisis_score_payload(
        cast(dict[str, Sequence[tuple[date, float]]], series_data),
        report_date=report_date,
    )
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
    warnings = [str(item) for item in cast(Iterable[object], raw_result.get("warnings", [])) if item]
    reason = "缺少全局分析日期，Crisis Score 使用自身输入最新日期补充证据"
    if reason not in warnings:
        warnings.insert(0, reason)
    enriched = dict(raw_result)
    if str(enriched.get("data_status") or "").lower() == "complete":
        enriched["data_status"] = "degraded"
    enriched["warnings"] = warnings
    return _capability_result_card(definition, enriched)

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
            for alias in cast(Sequence[str], requirement.get("aliases", ()))
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
    stale_inputs = [
        _stale_warning_from_missing(str(item["warning"]))
        for item in inputs
        if item["required"] and item["available"] and item.get("stale")
    ]
    warnings = [str(item) for item in cast(Iterable[object], result.get("warnings", [])) if item]
    for warning in [*missing_inputs, *stale_inputs]:
        if warning not in warnings:
            warnings.append(warning)

    enriched = dict(result)
    if (missing_inputs or stale_inputs) and str(enriched.get("data_status") or "").lower() == "complete":
        enriched["data_status"] = "degraded"
    enriched["warnings"] = warnings
    enriched["input_evidence"] = {
        "inputs": inputs,
        "missing_inputs": missing_inputs,
        "stale_inputs": stale_inputs,
        "sources": _unique_sorted_texts(item.get("source") for item in inputs),
        "latest_dates": _unique_sorted_texts(item.get("latest_date") for item in inputs),
    }
    return enriched

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
            for script_name in cast(Iterable[str], module["missing_scripts"])
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
