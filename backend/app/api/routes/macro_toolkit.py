from __future__ import annotations

import json  # noqa: F401  # kept: route-module namespace compatibility (tests/dir snapshot)
import uuid
from collections.abc import (
    Callable,  # noqa: F401  # kept: route-module namespace compatibility
    Iterable,
    Mapping,
)
from concurrent.futures import ThreadPoolExecutor
from datetime import (  # noqa: F401  # kept: route-module namespace compatibility
    UTC,
    date,
    datetime,
    timedelta,
    timezone,
)
from functools import lru_cache  # noqa: F401  # kept: route-module namespace compatibility
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from backend.app.api.deps import ensure_read_allowed
from backend.app.api.response_cache import (
    market_home_macro_analysis_cache_key,
    market_home_response_cache,
    market_home_strategy_summaries_cache_key,
)
from backend.app.governance.settings import (
    _REPO_ROOT,  # noqa: F401  # kept: route-module namespace compatibility
    get_settings,
)
from backend.app.repositories.cffex_member_rank_repo import (
    DEFAULT_CFFEX_CONTRACTS,
    table_stats,  # noqa: F401  # kept: route-module namespace compatibility
)
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import (
    macro_adversarial_signal_service,
    macro_etf_strategy_service,  # noqa: F401  # kept: route-module namespace compatibility
    macro_report_asset_service,
    macro_toolkit_refresh_receipt_service,
    macro_toolkit_service,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.macro_toolkit_analysis_service import (
    _a_share_stampede_risk_card,  # noqa: F401
    _analysis_data_health,
    _capability_primary_metric,  # noqa: F401
    _capability_result_card,
    _capability_result_evidence,  # noqa: F401
    _capability_result_headline,  # noqa: F401
    _capability_result_score,  # noqa: F401
    _credit_card,  # noqa: F401
    _crisis_commodity_candidate_admission,
    _crisis_commodity_candidate_approval_pack,
    _crisis_commodity_candidate_decision,  # noqa: F401
    _crisis_commodity_candidate_summary,  # noqa: F401
    _crisis_commodity_shadow_impact,
    _crisis_score_card,  # noqa: F401
    _float_or_none,
    _liquidity_card,  # noqa: F401
    _metric,  # noqa: F401
    _risk_appetite_card,  # noqa: F401
    _script_output_card,  # noqa: F401
    _unavailable_capability_result,
    _unique_sorted_texts,
    _unique_texts,
    select_primary_signal,
)
from backend.app.services.macro_toolkit_presentation import (
    _SOURCE_BACKFILL_TARGETS,
    _coerce_frame_date,  # noqa: F401
    _commodity_status_int,  # noqa: F401
    _commodity_status_text_set,  # noqa: F401
    _factor_snapshot_as_of_date,  # noqa: F401
    _factor_snapshot_date_status,  # noqa: F401
    _factor_snapshot_date_warnings,  # noqa: F401
    _factor_snapshot_provenance,  # noqa: F401
    _latest_source_check_date,
    _parse_report_date,
)

# 兼容性重导入：以下名字的实现已机械下沉到 services.macro_toolkit_route_support，
# 但必须保留在路由模块命名空间中——warmup 服务与大量测试直接从本模块导入或
# monkeypatch 这些属性；端点也继续用不带限定的全局名调用它们。
# 兼容性重导入：core_finance / pandas 名字统一经 support 透传，路由文件不再直接
# import pandas 或 backend.app.core_finance（tests 仍会 patch 本模块上的这些名字）。
from backend.app.services.macro_toolkit_route_support import (  # noqa: F401
    _ANALYSIS_INDICATORS,
    _CAPABILITY_DEFINITIONS,
    _CAPABILITY_INPUT_REQUIREMENTS,
    _CRISIS_COMMODITY_COVERAGE_INPUTS,
    _CRISIS_SCORE_INPUTS,
    _CURVE_ALIAS_POINTS,
    _CURVE_TYPE_TO_ID,
    _DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS,
    _EQUITY_STRATEGY_NO_SUMMARIES_WARNING,
    _EQUITY_STRATEGY_PRICE_CONTEXT_UNAVAILABLE_WARNING,
    _EQUITY_STRATEGY_PRICE_CONTEXT_UNSET,
    _HASON_BUSINESS_TZ,
    _HASON_MODULES,
    _HASON_OUTPUT_DATE_COLUMNS,
    _HASON_REQUIRED_OUTPUTS,
    _INDICATOR_RECENT_POINT_LIMIT,
    _MONTHLY_WIDE_FIELDS,
    _MULTI_ASSET_PRICE_INPUTS,
    _OBSERVATION_KEYS_CONFIG_PATH,
    _SOURCE_CHECK_ALIASES,
    _WIDE_FFILL_MAX_STALE_DAYS,
    _WIDE_SERIES_ALIASES,
    DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
    DEFAULT_DATA_SOURCES,
    FRESHNESS_TIER_EXPIRED,
    FRESHNESS_TIER_STALE,
    OMITTED_SOURCE_SCRIPTS,
    OUTPUT_DIR,
    REQUIRED_FACTOR_INPUTS,
    TOOLKIT_ROOT,
    MacroToolkitScript,
    _analysis_conclusion,
    _analysis_indicators,
    _analysis_runtime_status,
    _analysis_signal_cards,
    _analysis_warnings,
    _append_choice_stock_refresh_run,
    _capability_input_evidence_item,
    _cffex_freshness,
    _cffex_member_rank_status,
    _choice_stock_refresh_overview,
    _choice_stock_refresh_permission_payload,
    _choice_stock_refresh_run_payload,
    _choice_stock_refresh_status,
    _commodity_futures_refresh_permission_payload,
    _commodity_futures_refresh_summary,
    _commodity_ordered_products,
    _crisis_commodity_coverage,
    _crisis_commodity_coverage_item,
    _crisis_score_history,
    _current_gov_curve,
    _decision_summary_card,
    _decision_summary_observation_keys,
    _default_choice_stock_refresh_as_of_date,
    _default_source_backfill_start_date,
    _envelope,
    _equity_strategy_payload_data_status,
    _equity_strategy_payload_warnings,
    _equity_strategy_summary_data_status,
    _evidence_rows,
    _first_available_source_check,
    _frame_to_crisis_points,
    _gate_analysis_conclusion_on_refresh_receipt,
    _hason_module_payload,
    _hason_output_content_dates,
    _hason_output_freshness,
    _hason_output_modified_date,
    _hason_runtime_output_payload,
    _hason_runtime_output_status,
    _hason_runtime_outputs,
    _hason_source_trace,
    _indicator_payload,
    _input_cadence_for_field,
    _latest_choice_stock_inflight_refresh,
    _latest_crisis_input_date,
    _latest_factor_snapshot_from_price_context,
    _latest_indicator_date,
    _latest_strategy_as_of_date,
    _latest_wide_field_observation,
    _latest_wide_field_value,
    _load_decision_summary_observation_keys,
    _load_macro_capability_context,
    _load_macro_wide_rows,
    _macro_commodity_product_codes,
    _macro_etf_strategy_snapshot_for_toolkit,
    _merrill_regime_from_payload,
    _model_chain_artifacts_all_ok,
    _real_equity_strategy_summaries,
    _real_low_crowding_regime_multifactor_summary,
    _real_multi_factor_summary,
    _risk_tensor_to_liquidity_inputs,
    _run_capability,
    _sample_strategy_observations,
    _script_payload,
    _script_warnings,
    _serialize_provenance_leg,
    _source_check,
    _source_check_payload,
    _stale_warning_from_missing,
    _strategy_summaries_use_choice_stock,
    _strategy_summaries_use_stock_factor_snapshot,
    _strategy_summary,
    _unavailable_equity_strategy_summary,
    analyze_cross_market_linkage,
    assess_freshness,
    build_bond_portfolio_profile,
    build_crisis_score_history_payload,
    build_curve_history,
    classify_low_crowding_market_regime,
    clean_low_crowding_observations,
    clear_system_macro_source_cache,
    compute_a_share_stampede_risk,
    compute_credit_spread_risk,
    compute_crisis_score_payload,
    compute_cta_trend_payload,
    compute_dcc_garch_payload,
    compute_economic_cycle,
    compute_equity_shadow_portfolio_report,
    compute_leading_indicator,
    compute_liquidity_stress_test,
    compute_low_crowding_scores,
    compute_macro_portfolio_impact,
    compute_merrill_clock_payload,
    compute_monetary_policy_stance,
    compute_rate_turning_point,
    compute_risk_parity_payload,
    compute_yield_curve_shape,
    enrich_wide_with_curve_market_fields,
    evaluate_crisis_commodity_shadow,
    iter_toolkit_scripts,
    load_a_share_stampede_risk_config,
    load_series_by_alias,
    load_series_by_aliases,
    low_crowding_multifactor_selection,
    mean_reversion_momentum_strategy,
    moving_average_strategy,
    multi_factor_selection,
    pd,
    sort_wide_rows_for_macro,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

# 保留模块级注解声明：原 _HASON_MODULES 顶层注解随实现下沉后，模块 __annotations__
# 仍需存在（dir() 快照兼容）。本声明不重新赋值，名字仍绑定 support 中的定义。
_HASON_MODULES: tuple[dict[str, object], ...]

router = APIRouter(prefix="/ui/macro/toolkit", tags=["macro-toolkit"])


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
    refresh_receipt_health = (
        macro_toolkit_refresh_receipt_service.load_macro_toolkit_refresh_receipt_health()
    )
    return market_home_response_cache.get_or_build(
        market_home_macro_analysis_cache_key(
            settings.duckdb_path,
            detail,
            history_limit=resolved_history_limit if detail == "full" else None,
            freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
        ),
        lambda: _build_macro_toolkit_analysis(
            detail,
            history_limit=resolved_history_limit,
            refresh_receipt_health=refresh_receipt_health,
        ),
    )


def _build_macro_toolkit_analysis(
    detail: str,
    *,
    history_limit: int = DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
    refresh_receipt_health: (
        macro_toolkit_refresh_receipt_service.MacroToolkitRefreshReceiptHealth | None
    ) = None,
) -> dict[str, object]:
    settings = get_settings()
    indicators = _analysis_indicators(settings.duckdb_path)
    indicator_by_key = {str(item["key"]): item for item in indicators}
    output_files = _output_files()
    report_bundle = macro_report_asset_service.load_report_bundle(
        OUTPUT_DIR / macro_report_asset_service.BUNDLE_DIRNAME
    )
    analysis_date = _latest_indicator_date(indicators)
    readiness = macro_toolkit_service.macro_model_readiness(
        output_dir=OUTPUT_DIR,
        reference_date=analysis_date,
    )
    base_signal_cards = _analysis_signal_cards(
        indicator_by_key,
        output_files,
        [],
        None,
        capabilities_deferred=True,
    )
    if detail == "core":
        a_share_risk = None
        capability_results: list[dict[str, object]] = []
        strategy_summaries: list[dict[str, object]] = []
        strategy_data_status = _equity_strategy_payload_data_status(strategy_summaries, deferred=True)
        source_checks: list[dict[str, object]] = []
        capabilities: list[dict[str, object]] = []
        runtime_status = _analysis_runtime_status("core")
        signal_cards = base_signal_cards
        primary_signal = select_primary_signal(
            signal_cards,
            a_share_risk=a_share_risk,
            capability_results=capability_results,
            capabilities_deferred=True,
        )
    else:
        a_share_risk, capability_results, strategy_summaries = _build_macro_toolkit_full_analysis_blocks(
            settings.duckdb_path,
            analysis_date,
            history_limit=history_limit,
        )
        strategy_data_status = _equity_strategy_payload_data_status(strategy_summaries)
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
        )
        primary_signal = select_primary_signal(
            signal_cards,
            a_share_risk=a_share_risk,
            capability_results=capability_results,
            capabilities_deferred=False,
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
    conclusion = _analysis_conclusion(base_signal_cards, coverage)
    conclusion["basis"] = {
        "source": "core_signal_cards",
        "signal_cards": [
            {"key": str(card["key"]), "tone": str(card["tone"])}
            for card in base_signal_cards
        ],
    }
    warnings = _analysis_warnings(coverage)
    if refresh_receipt_health is not None:
        conclusion = _gate_analysis_conclusion_on_refresh_receipt(
            conclusion,
            warnings,
            refresh_receipt_health,
        )
    data_health = _analysis_data_health(
        indicators=indicators,
        source_checks=source_checks,
        capability_results=capability_results,
        capabilities=capabilities,
        runtime_status=runtime_status,
        warnings=warnings,
        reference_date=analysis_date,
    )
    if refresh_receipt_health is not None:
        data_health["refresh_receipt"] = refresh_receipt_health.as_payload()
    return _envelope(
        "macro_toolkit.analysis",
        {
            "default_data_sources": list(DEFAULT_DATA_SOURCES),
            "as_of_date": analysis_date,
            "conclusion": conclusion,
            "coverage": coverage,
            "indicators": indicators,
            "signal_cards": signal_cards,
            "primary_signal": primary_signal,
            "hason_strategy": hason_strategy,
            "a_share_risk": a_share_risk,
            "capability_results": capability_results,
            "strategy_summaries": strategy_summaries,
            "strategy_data_status": strategy_data_status,
            "output_files": output_files,
            "report_bundle": report_bundle,
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
        quality_flag="warning",
        as_of_date=analysis_date,
    )


@router.get("/report-bundle/{artifact_id}")
def macro_toolkit_report_bundle_artifact(
    artifact_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Response:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    bundle_dir = OUTPUT_DIR / macro_report_asset_service.BUNDLE_DIRNAME
    try:
        artifact = macro_report_asset_service.read_report_artifact(bundle_dir, artifact_id)
    except (
        macro_report_asset_service.ReportBundleNotFoundError,
        macro_report_asset_service.ReportArtifactNotFoundError,
    ) as exc:
        raise HTTPException(status_code=404, detail=exc.reason) from exc
    except macro_report_asset_service.ReportBundleInvalidError as exc:
        raise HTTPException(status_code=409, detail=exc.reason) from exc
    encoded_filename = quote(artifact.filename, safe="")
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
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
    strategy_data_status = _equity_strategy_payload_data_status(
        strategies,
        price_context_unavailable=price_context is None and not strategies,
    )
    warnings = _equity_strategy_payload_warnings(strategy_data_status)
    strategy_as_of_date = _latest_strategy_as_of_date(strategies)
    shadow_portfolio_report = compute_equity_shadow_portfolio_report(
        settings.duckdb_path,
        latest_factor_snapshot=_latest_factor_snapshot_from_price_context(price_context),
    )
    macro_etf_strategy = _macro_etf_strategy_snapshot_for_toolkit(
        duckdb_path=settings.duckdb_path,
        as_of_date=strategy_as_of_date,
    )
    macro_etf_data_status = macro_etf_strategy.get("data_status")
    macro_etf_ready = (
        isinstance(macro_etf_data_status, Mapping)
        and macro_etf_data_status.get("status") == "ready"
        and macro_etf_data_status.get("dual_frequency_status") == "ready"
    )
    return _envelope(
        "macro_toolkit.analysis.strategy_summaries",
        {
            "strategy_summaries": strategies,
            "strategy_data_status": strategy_data_status,
            "shadow_portfolio_report": shadow_portfolio_report,
            "macro_etf_strategy": macro_etf_strategy,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                reference_date=strategy_as_of_date,
            ),
            "warnings": warnings,
        },
        quality_flag="ok" if macro_etf_ready else "warning",
        as_of_date=strategy_as_of_date,
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


@router.get("/model-chain-results")
def macro_toolkit_model_chain_results(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    chain_result = macro_toolkit_service.build_model_chain_results(OUTPUT_DIR)
    return _envelope(
        "macro_toolkit.model_chain_results",
        chain_result,
        quality_flag="ok" if _model_chain_artifacts_all_ok(chain_result) else "warning",
        fallback_mode="none",
        as_of_date=chain_result.get("as_of_date"),
    )


@router.post("/cffex-member-rank/refresh", status_code=202)
def macro_toolkit_refresh_cffex_member_rank(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request: CffexMemberRankRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or CffexMemberRankRefreshRequest()
    settings = get_settings()
    _ensure_cffex_member_rank_refresh_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.refresh_cffex_member_rank(
            duckdb_path=settings.duckdb_path,
            governance_path=settings.governance_path,
            trade_date=refresh_request.trade_date,
            contracts=tuple(refresh_request.contracts or DEFAULT_CFFEX_CONTRACTS),
            sources=tuple(refresh_request.sources or ["choice", "tushare"]),
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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


@router.get("/cffex-member-rank/refresh-status")
def macro_toolkit_cffex_member_rank_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.cffex_member_rank_refresh_status(
            settings.governance_path,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    report_date = str(
        refresh.get("trade_date") or refresh.get("report_date") or ""
    )[:10] or None
    return _envelope(
        "macro_toolkit.cffex_member_rank_refresh_status",
        {
            "refresh": refresh,
            "cffex_member_rank": _cffex_member_rank_status(
                settings.duckdb_path,
                reference_date=report_date,
            ),
        },
        quality_flag=(
            "ok" if str(refresh.get("status") or "") == "completed" else "warning"
        ),
        as_of_date=report_date,
    )


@router.post("/choice-stock/refresh", status_code=202)
def macro_toolkit_refresh_choice_stock(
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
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
        quality_flag=(
            "ok" if str(status.get("status") or "") == "completed" else "warning"
        ),
    )


@router.post("/source-backfill/refresh", status_code=202)
def macro_toolkit_refresh_source_backfill(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: SourceBackfillRefreshRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_source_backfill_refresh_allowed(auth, settings)
    target = _source_backfill_target(request.alias)
    start_date = request.start_date or _default_source_backfill_start_date(request.end_date)
    end_date = request.end_date or date.today().isoformat()
    try:
        refresh = macro_toolkit_service.queue_macro_source_backfill(
            duckdb_path=str(settings.duckdb_path),
            governance_path=str(settings.governance_path),
            alias=request.alias,
            series_id=str(target["series_id"]),
            series_name=str(target["series_name"]),
            backfill_mode=str(target.get("backfill_mode") or "macro_series"),
            start_date=start_date,
            end_date=end_date,
            sources=tuple(request.sources or list(target["default_sources"])),
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _envelope(
        "macro_toolkit.source_backfill_refresh",
        {"refresh": refresh.payload},
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.get("/source-backfill/refresh-status")
def macro_toolkit_source_backfill_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.macro_source_backfill_refresh_status(
            settings.governance_path,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    report_date = str(
        refresh.get("end_date") or refresh.get("report_date") or ""
    )[:10] or None
    return _envelope(
        "macro_toolkit.source_backfill_refresh_status",
        {"refresh": refresh},
        quality_flag=(
            "ok" if str(refresh.get("status") or "") == "completed" else "warning"
        ),
        as_of_date=report_date,
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
    unknown = tuple(product for product in normalized if product not in _macro_commodity_product_codes())
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
    ensure_read_allowed(auth, "macro_toolkit", settings=settings, authorize=ensure_user_allowed)


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
        "data_tables": [str(table) for table in definition.get("data_tables", ())],
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
    proxy_rows, bucket_rows, total_assets = _risk_tensor_to_liquidity_inputs(risk_tensor)
    portfolio_profile = build_bond_portfolio_profile(positions, parsed_report_date)
    current_curve = _current_gov_curve(curve_rows, parsed_report_date)

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
        str(definition["key"]): _capability_result_card(definition, raw_results.get(str(definition["key"])))
        for definition in _CAPABILITY_DEFINITIONS
        if definition["key"] != "decision_summary"
    }
    cards: list[dict[str, object]] = []
    for definition in _CAPABILITY_DEFINITIONS:
        if definition["key"] == "decision_summary":
            cards.append(
                _decision_summary_card(definition, list(non_decision_cards.values()), report_date)
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
    except Exception as exc:  # pragma: no cover - displayed as unavailable strategy evidence
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
        return _real_equity_strategy_summaries(price_context)
    except Exception as exc:  # pragma: no cover - displayed as unavailable strategy evidence
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
    tables_used = [str(item) for item in context.get("tables_used", [])]
    payload["tables_used"] = _unique_texts([*payload.get("tables_used", []), *tables_used])
    if context.get("warnings"):
        payload["warnings"] = _unique_texts([*payload.get("warnings", []), *context["warnings"]])
        if payload.get("status") == "complete":
            payload["status"] = "degraded"
    return payload


def _load_a_share_stampede_risk_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    return macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)


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
    stale_inputs = [
        _stale_warning_from_missing(str(item["warning"]))
        for item in inputs
        if item["required"] and item["available"] and item.get("stale")
    ]
    warnings = [str(item) for item in result.get("warnings", []) if item]
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


def _load_macro_curve_rows(duckdb_path: str | Path, report_date: date) -> list[dict[str, object]]:
    return macro_toolkit_service.load_macro_curve_rows(duckdb_path, report_date)


def _load_latest_risk_tensor_row(
    duckdb_path: str | Path,
    report_date: date,
) -> dict[str, object] | None:
    return macro_toolkit_service.load_latest_risk_tensor_row(duckdb_path, report_date)


def _load_latest_bond_positions(
    duckdb_path: str | Path,
    report_date: date,
) -> list[dict[str, object]]:
    return macro_toolkit_service.load_latest_bond_positions(duckdb_path, report_date)


def __getattr__(name: str) -> object:
    # Keep `_DECISION_SUMMARY_OBSERVATION_KEYS` as a compatible lazy attribute for tests.
    if name == "_DECISION_SUMMARY_OBSERVATION_KEYS":
        return _decision_summary_observation_keys()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
