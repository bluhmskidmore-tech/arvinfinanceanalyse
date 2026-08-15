from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from backend.app.core_finance.macro_bond_linkage import (
    ENVIRONMENT_COMPOSITE_FORMULA_VERSION,
    EquityBondSpreadSignal,
    MacroBondCorrelation,
    MegaCapEquitySignal,
    build_macro_bond_research_output,
    compute_macro_bond_correlations,
    compute_macro_environment_score,
    estimate_macro_impact_on_portfolio,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.macro_bond_linkage_repo import MacroBondLinkageRepository
from backend.app.schemas.macro_bond_linkage import (
    MacroBondLinkageMethodMeta,
    MacroBondLinkageMethodVariant,
    MacroBondLinkageMethodVariants,
    MacroBondLinkageResponse,
)
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache

RULE_VERSION = "rv_macro_bond_linkage_v2_liquidity_inverted"
CACHE_VERSION = "cv_macro_bond_linkage_v2_liquidity_inverted"
RESULT_KIND = "macro_bond_linkage.analysis"
EMPTY_SOURCE_VERSION = "sv_macro_bond_linkage_empty"
LOOKBACK_DAYS = 365
MIN_TRADE_DATES = 30
TOP_CORRELATION_LIMIT = 10
MACRO_BOND_LINKAGE_COMPONENTS_CACHE_NAME = "macro_bond_linkage_components"
MACRO_BOND_LINKAGE_COMPONENTS_CACHE_TTL_SECONDS = 300.0
MACRO_ENVIRONMENT_CONTEXT_RESULT_KIND = "macro_bond_linkage.environment_context"
MACRO_ENVIRONMENT_CONTEXT_CACHE_VERSION = "cv_macro_environment_context_v2_liquidity_inverted"
MACRO_ENVIRONMENT_CONTEXT_CACHE_NAME = "macro_environment_context"
MACRO_ENVIRONMENT_CONTEXT_CACHE_TTL_SECONDS = 300.0
MACRO_CONTEXT_CONTRACT_VERSION = "rv_macro_context_v1"
MACRO_CONTEXT_MIN_EVIDENCE_ROWS = 30
MACRO_CONTEXT_SCORE_FIELDS = (
    "rate_direction_score",
    "liquidity_score",
    "growth_score",
    "inflation_score",
    "composite_score",
)
MACRO_CONTEXT_SCORE_POLARITY = {
    "rate_direction_score": "positive=bond_unfavorable_rate_up_pressure",
    "liquidity_score": "positive=liquidity_easing",
    "growth_score": "positive=bond_unfavorable_growth_strength",
    "inflation_score": "positive=bond_unfavorable_inflation_pressure",
    "composite_score": "positive=bond_unfavorable_restrictive_macro_pressure",
}
MACRO_CONTEXT_COMPOSITE_FORMULA = (
    "0.4*rate_direction_score - 0.3*liquidity_score "
    "+ 0.2*growth_score + 0.1*inflation_score"
)
MACRO_CONTEXT_COMPOSITE_FORMULA_VERSION = ENVIRONMENT_COMPOSITE_FORMULA_VERSION
# 与 core_finance contributing_factors 的 category 词表保持一致。
MACRO_ENVIRONMENT_EVIDENCE_CATEGORIES = ("rate", "liquidity", "growth", "inflation")
MACRO_ENVIRONMENT_SIGNAL_UNAVAILABLE_TEXT = "宏观环境评分缺少可用指标证据，暂无信号。"
MACRO_ENVIRONMENT_SIGNAL_UNAVAILABLE_WARNING = (
    "宏观环境评分缺少可用指标证据，久期等方向性判断已置为暂无信号。"
)

CacheKey = tuple[str, int, int, str, str, str]


def get_macro_bond_linkage(report_date: date) -> dict[str, object]:
    settings = get_settings()
    duckdb_path = str(settings.duckdb_path)
    cache_key = _macro_bond_linkage_components_cache_key(
        duckdb_path=duckdb_path,
        report_date=report_date,
    )

    def _produce() -> dict[str, object]:
        return _get_macro_bond_linkage_uncached(
            report_date=report_date,
            duckdb_path=duckdb_path,
        )

    if cache_key is None:
        return _refresh_macro_bond_linkage_envelope(_produce(), cache_hit=False)

    cache: InMemoryTTLCache[CacheKey, dict[str, object]] = get_runtime_cache(
        MACRO_BOND_LINKAGE_COMPONENTS_CACHE_NAME,
        ttl_seconds=MACRO_BOND_LINKAGE_COMPONENTS_CACHE_TTL_SECONDS,
    )
    envelope, cache_hit = _cached_envelope(cache, cache_key, _produce)
    return _refresh_macro_bond_linkage_envelope(envelope, cache_hit=cache_hit)


def get_macro_environment_context(report_date: date) -> dict[str, object]:
    settings = get_settings()
    duckdb_path = str(settings.duckdb_path)
    cache_key = _macro_environment_context_cache_key(
        duckdb_path=duckdb_path,
        report_date=report_date,
    )

    def _produce() -> dict[str, object]:
        return _get_macro_environment_context_uncached(
            report_date=report_date,
            duckdb_path=duckdb_path,
        )

    if cache_key is None:
        return _refresh_macro_bond_linkage_envelope(_produce(), cache_hit=False)

    cache: InMemoryTTLCache[CacheKey, dict[str, object]] = get_runtime_cache(
        MACRO_ENVIRONMENT_CONTEXT_CACHE_NAME,
        ttl_seconds=MACRO_ENVIRONMENT_CONTEXT_CACHE_TTL_SECONDS,
    )
    envelope, cache_hit = _cached_envelope(cache, cache_key, _produce)
    return _refresh_macro_bond_linkage_envelope(envelope, cache_hit=cache_hit)


def _cached_envelope(
    cache: InMemoryTTLCache[CacheKey, dict[str, object]],
    cache_key: CacheKey,
    producer: Callable[[], dict[str, object]],
) -> tuple[dict[str, object], bool]:
    produced = False

    def _produce_once() -> dict[str, object]:
        nonlocal produced
        produced = True
        return producer()

    envelope = cache.get_or_set(cache_key, _produce_once)
    return envelope, not produced


def get_macro_context_v1(report_date: date, *, as_of_date: str | None = None) -> dict[str, object]:
    macro_envelope = get_macro_environment_context(report_date)
    return build_macro_context_v1(
        as_of_date=as_of_date or report_date.isoformat(),
        macro_payload=_mapping(macro_envelope.get("result")),
        macro_meta=_mapping(macro_envelope.get("result_meta")),
    )


def build_macro_context_v1(
    *,
    as_of_date: str,
    macro_payload: dict[str, object],
    macro_meta: dict[str, object],
) -> dict[str, object]:
    environment_score = _mapping(macro_payload.get("environment_score"))
    warnings = _string_list(macro_payload.get("warnings"))
    evidence_rows = _optional_count(_meta_evidence_rows(macro_meta)) or 0
    source_version = _optional_text(_meta_source_version(macro_meta))
    vendor_version = _optional_text(_meta_vendor_version(macro_meta))
    rule_version = _optional_text(macro_meta.get("rule_version"))
    cache_version = _optional_text(macro_meta.get("cache_version"))
    quality_flag = _optional_text(_meta_quality_flag(macro_meta)) or "warning"
    vendor_status = _optional_text(_meta_vendor_status(macro_meta)) or "vendor_unavailable"
    fallback_mode = _optional_text(_meta_fallback_mode(macro_meta)) or "none"
    data_state = _macro_context_data_state(
        environment_score=environment_score,
        warnings=warnings,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
    )
    coverage_ratio = _macro_context_coverage_ratio(evidence_rows)
    freshness_score = 1.0 if environment_score else 0.0
    confidence_score = _macro_context_confidence_score(
        coverage_ratio=coverage_ratio,
        freshness_score=freshness_score,
        data_state=data_state,
    )
    dimension_scores = {
        field: _safe_optional_float(environment_score.get(field))
        for field in MACRO_CONTEXT_SCORE_FIELDS
    }
    report_date_text = (
        _optional_text(environment_score.get("report_date"))
        or _optional_text(macro_payload.get("report_date"))
        or as_of_date
    )
    readiness_reasons = _macro_context_readiness_reasons(
        environment_score=environment_score,
        warnings=warnings,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        coverage_ratio=coverage_ratio,
    )
    return {
        "macro_context_id": _macro_context_id(
            {
                "contract_version": MACRO_CONTEXT_CONTRACT_VERSION,
                "asof_date": as_of_date,
                "report_date": report_date_text,
                "source_version": source_version,
                "vendor_version": vendor_version,
                "rule_version": rule_version,
                "cache_version": cache_version,
                "data_state": data_state,
                "dimension_scores": dimension_scores,
                "composite_formula_version": MACRO_CONTEXT_COMPOSITE_FORMULA_VERSION,
            }
        ),
        "macro_contract_version": MACRO_CONTEXT_CONTRACT_VERSION,
        "asof_date": as_of_date,
        "report_date": report_date_text,
        "data_state": data_state,
        "coverage_ratio": coverage_ratio,
        "freshness_score": freshness_score,
        "confidence_score": confidence_score,
        "fallback_mode": fallback_mode,
        "dimension_scores": dimension_scores,
        "score_polarity": MACRO_CONTEXT_SCORE_POLARITY,
        "composite_formula": MACRO_CONTEXT_COMPOSITE_FORMULA,
        "composite_formula_version": MACRO_CONTEXT_COMPOSITE_FORMULA_VERSION,
        "readiness_reasons": readiness_reasons,
        "quality_flag": quality_flag,
        "vendor_status": vendor_status,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "rule_version": rule_version,
        "cache_version": cache_version,
        "evidence_rows": evidence_rows,
        "warning_count": len(warnings),
    }


def _macro_environment_context_cache_key(
    *,
    duckdb_path: str,
    report_date: date,
) -> tuple[str, int, int, str, str, str] | None:
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        stat = path.stat()
        resolved_path = str(path.resolve())
    except OSError:
        return None
    return (
        resolved_path,
        stat.st_mtime_ns,
        stat.st_size,
        report_date.isoformat(),
        RULE_VERSION,
        MACRO_ENVIRONMENT_CONTEXT_CACHE_VERSION,
    )


def _get_macro_environment_context_uncached(
    *,
    report_date: date,
    duckdb_path: str,
) -> dict[str, object]:
    computed_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []
    repo = MacroBondLinkageRepository(duckdb_path, guard_path_exists=True)
    with repo.scoped_connection() as conn:
        if conn is None:
            warnings.append("DuckDB 只读连接不可用，暂无法生成宏观环境评分。")
            return _build_macro_environment_context_envelope(
                report_date=report_date,
                computed_at=computed_at,
                environment_score={},
                warnings=warnings,
                source_versions=[EMPTY_SOURCE_VERSION],
                vendor_versions=["vv_none"],
                upstream_rule_versions=[],
                evidence_rows=0,
            )
        macro_inputs = _load_macro_inputs(repo, report_date, conn=conn)

    environment_score_payload: dict[str, Any] = {}
    if macro_inputs["trade_date_count"] < MIN_TRADE_DATES:
        warnings.append("fact_choice_macro_daily 数据点不足（少于 30 个交易日），暂不生成宏观环境评分。")
    elif not macro_inputs["series"]:
        warnings.append("fact_choice_macro_daily 缺少可用宏观序列。")
    else:
        environment_score = compute_macro_environment_score(
            macro_latest=macro_inputs["latest"],
            macro_history=macro_inputs["series"],
            lookback_days=90,
        )
        warnings.extend(environment_score.warnings)
        environment_score_payload, _signal_status = _apply_environment_signal_status(
            _json_safe(environment_score),
            warnings=warnings,
        )

    return _build_macro_environment_context_envelope(
        report_date=report_date,
        computed_at=computed_at,
        environment_score=environment_score_payload,
        warnings=_dedupe_preserve_order(warnings),
        source_versions=[*macro_inputs["source_versions"]],
        vendor_versions=[*macro_inputs["vendor_versions"]],
        upstream_rule_versions=[*macro_inputs["rule_versions"]],
        evidence_rows=int(macro_inputs["trade_date_count"]),
    )


def _macro_bond_linkage_components_cache_key(
    *,
    duckdb_path: str,
    report_date: date,
) -> tuple[str, int, int, str, str, str] | None:
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        stat = path.stat()
        resolved_path = str(path.resolve())
    except OSError:
        return None
    return (
        resolved_path,
        stat.st_mtime_ns,
        stat.st_size,
        report_date.isoformat(),
        RULE_VERSION,
        CACHE_VERSION,
    )


def _refresh_macro_bond_linkage_envelope(
    envelope: dict[str, object],
    *,
    cache_hit: bool,
) -> dict[str, object]:
    refreshed = dict(envelope)
    result_meta = dict(cast(dict[str, object], refreshed.get("result_meta") or {}))
    result = dict(cast(dict[str, object], refreshed.get("result") or {}))
    result_meta["trace_id"] = _trace_id()
    # computed_at 必须保留真实计算时间；served_at 记录本次响应时间，两者之差即缓存年龄。
    result["served_at"] = datetime.now(UTC).isoformat()
    result["cache_hit"] = cache_hit
    refreshed["result_meta"] = result_meta
    refreshed["result"] = result
    return refreshed


def _environment_evidence_categories(environment_score: dict[str, Any]) -> list[str]:
    factors = environment_score.get("contributing_factors")
    if not isinstance(factors, list):
        return []
    covered = {
        str(factor.get("category") or "").strip()
        for factor in factors
        if isinstance(factor, dict)
    }
    return [category for category in MACRO_ENVIRONMENT_EVIDENCE_CATEGORIES if category in covered]


def _apply_environment_signal_status(
    environment_score: dict[str, Any],
    *,
    warnings: list[str],
) -> tuple[dict[str, Any], str]:
    """标注环境评分的证据覆盖度；证据全缺时不得输出久期方向判断。

    ``compute_macro_environment_score`` 在指标缺失时把分项分数默认为 0，合成分随之落到
    中性区间并给出"维持当前久期配置"。这里按 contributing_factors 判断真实证据覆盖，
    零覆盖时把方向性文案替换为显式"暂无信号"。
    """
    if not environment_score:
        return environment_score, "unavailable"

    covered = _environment_evidence_categories(environment_score)
    if not covered:
        signal_status = "unavailable"
    elif len(covered) < len(MACRO_ENVIRONMENT_EVIDENCE_CATEGORIES):
        signal_status = "partial"
    else:
        signal_status = "ready"

    gated = dict(environment_score)
    gated["signal_status"] = signal_status
    gated["signal_evidence_categories"] = covered
    gated["signal_missing_categories"] = [
        category for category in MACRO_ENVIRONMENT_EVIDENCE_CATEGORIES if category not in covered
    ]
    if signal_status == "unavailable":
        gated["rate_direction"] = "unknown"
        gated["signal_description"] = MACRO_ENVIRONMENT_SIGNAL_UNAVAILABLE_TEXT
        warnings.append(MACRO_ENVIRONMENT_SIGNAL_UNAVAILABLE_WARNING)
    return gated, signal_status


def _pending_signal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for row in rows:
        updated = {
            **row,
            "status": "pending_signal",
            "stance": "neutral",
            "summary": MACRO_ENVIRONMENT_SIGNAL_UNAVAILABLE_TEXT,
        }
        if "confidence" in updated:
            updated["confidence"] = "low"
        pending.append(updated)
    return pending


def _build_macro_environment_context_envelope(
    *,
    report_date: date,
    computed_at: str,
    environment_score: dict[str, Any],
    warnings: list[str],
    source_versions: list[str],
    vendor_versions: list[str],
    upstream_rule_versions: list[str],
    evidence_rows: int,
) -> dict[str, object]:
    meta = build_analytical_result_meta(
        trace_id=_trace_id(),
        result_kind=MACRO_ENVIRONMENT_CONTEXT_RESULT_KIND,
        cache_version=MACRO_ENVIRONMENT_CONTEXT_CACHE_VERSION,
        source_version=_aggregate_lineage(source_versions, EMPTY_SOURCE_VERSION),
        rule_version=_aggregate_lineage([RULE_VERSION, *upstream_rule_versions], RULE_VERSION),
        vendor_version=_aggregate_lineage(vendor_versions, "vv_none"),
        quality_flag="warning" if warnings else "ok",
        vendor_status="vendor_unavailable" if not environment_score else "ok",
        fallback_mode="none",
        tables_used=["fact_choice_macro_daily"],
        evidence_rows=evidence_rows,
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload={
            "report_date": report_date.isoformat(),
            "environment_score": environment_score,
            "warnings": warnings,
            "computed_at": computed_at,
        },
    )


def _get_macro_bond_linkage_uncached(
    *,
    report_date: date,
    duckdb_path: str,
) -> dict[str, object]:
    computed_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []
    repo = MacroBondLinkageRepository(duckdb_path, guard_path_exists=True)
    with repo.scoped_connection() as conn:
        if conn is None:
            warnings.append("DuckDB 只读连接不可用，暂无法生成宏观-债市联动分析。")
            return _build_response_envelope(
                report_date=report_date,
                computed_at=computed_at,
                environment_score={},
                portfolio_impact={},
                top_correlations=[],
                method_variants=_empty_method_variants(),
                research_views=[],
                transmission_axes=[],
                warnings=warnings,
                source_versions=[EMPTY_SOURCE_VERSION],
                vendor_versions=["vv_none"],
                upstream_rule_versions=[],
            )
        macro_inputs = _load_macro_inputs(repo, report_date, conn=conn)
        yield_inputs = _load_yield_inputs(repo, report_date, conn=conn)
        portfolio_metrics = _load_portfolio_metrics(repo, report_date, conn=conn)

    warnings.extend(portfolio_metrics["warnings"])

    if macro_inputs["trade_date_count"] < MIN_TRADE_DATES:
        warnings.append("fact_choice_macro_daily 数据点不足（少于 30 个交易日），暂不生成宏观-债市联动分析。")
        return _build_response_envelope(
            report_date=report_date,
            computed_at=computed_at,
            environment_score={},
            portfolio_impact={},
            top_correlations=[],
            method_variants=_empty_method_variants(),
            research_views=[],
            transmission_axes=[],
            warnings=_dedupe_preserve_order(warnings),
            source_versions=[
                *macro_inputs["source_versions"],
                *yield_inputs["source_versions"],
                portfolio_metrics["source_version"],
            ],
            vendor_versions=[
                *macro_inputs["vendor_versions"],
                *yield_inputs["vendor_versions"],
            ],
            upstream_rule_versions=[
                *macro_inputs["rule_versions"],
                *yield_inputs["rule_versions"],
                portfolio_metrics["rule_version"],
            ],
        )

    if not macro_inputs["series"]:
        warnings.append("fact_choice_macro_daily 缺少可用宏观序列。")
    if not yield_inputs["series"]:
        warnings.append("yield_curve_daily 缺少可用收益率曲线序列。")

    top_correlations: list[dict[str, Any]] = []
    method_variants = _empty_method_variants()
    environment_score_payload: dict[str, Any] = {}
    portfolio_impact_payload: dict[str, Any] = {}
    research_views: list[dict[str, Any]] = []
    transmission_axes: list[dict[str, Any]] = []

    if macro_inputs["series"] and yield_inputs["series"]:
        conservative_corrs = compute_macro_bond_correlations(
            macro_inputs["series"],
            yield_inputs["series"],
            lookback_days=LOOKBACK_DAYS,
            alignment_mode="conservative",
        )
        market_timing_corrs = compute_macro_bond_correlations(
            macro_inputs["series"],
            yield_inputs["series"],
            lookback_days=LOOKBACK_DAYS,
            alignment_mode="market_timing",
        )
        conservative_rows = _ranked_correlation_payloads(
            conservative_corrs,
            macro_inputs["series_name_map"],
            alignment_mode="conservative",
        )
        market_timing_rows = _ranked_correlation_payloads(
            market_timing_corrs,
            macro_inputs["series_name_map"],
            alignment_mode="market_timing",
        )
        top_correlations = conservative_rows
        method_variants = MacroBondLinkageMethodVariants(
            conservative=MacroBondLinkageMethodVariant(
                method_meta=MacroBondLinkageMethodMeta(variant="conservative"),
                top_correlations=conservative_rows,
            ),
            market_timing=MacroBondLinkageMethodVariant(
                method_meta=MacroBondLinkageMethodMeta(variant="market_timing"),
                top_correlations=market_timing_rows,
            ),
        )

        environment_score = compute_macro_environment_score(
            macro_latest=macro_inputs["latest"],
            macro_history=macro_inputs["series"],
            lookback_days=90,
        )
        warnings.extend(environment_score.warnings)
        environment_score_payload, signal_status = _apply_environment_signal_status(
            _json_safe(environment_score),
            warnings=warnings,
        )
        portfolio_impact_payload = _json_safe(
            estimate_macro_impact_on_portfolio(
                macro_environment=environment_score,
                portfolio_dv01=portfolio_metrics["portfolio_dv01"],
                portfolio_cs01=portfolio_metrics["portfolio_cs01"],
                portfolio_market_value=portfolio_metrics["portfolio_market_value"],
            )
        )
        equity_bond_signal = None
        mega_cap_signal = None
        equity_bond_signal, mega_cap_signal, landed_axis_warnings = _load_landed_equity_research_signals(
            duckdb_path=duckdb_path,
            report_date=report_date,
            macro_latest=macro_inputs["latest"],
        )
        warnings.extend(landed_axis_warnings)
        research_view_rows, transmission_axis_rows = build_macro_bond_research_output(
            environment_score,
            conservative_corrs,
            equity_bond_spread_signal=equity_bond_signal,
            mega_cap_equity_signal=mega_cap_signal,
        )
        research_views = _json_safe(research_view_rows)
        transmission_axes = _json_safe(transmission_axis_rows)
        if signal_status == "unavailable":
            research_views = _pending_signal_rows(research_views)
            transmission_axes = _pending_signal_rows(transmission_axes)
    return _build_response_envelope(
        report_date=report_date,
        computed_at=computed_at,
        environment_score=environment_score_payload,
        portfolio_impact=portfolio_impact_payload,
        top_correlations=top_correlations,
        method_variants=method_variants,
        research_views=research_views,
        transmission_axes=transmission_axes,
        warnings=_dedupe_preserve_order(warnings),
        source_versions=[
            *macro_inputs["source_versions"],
            *yield_inputs["source_versions"],
            portfolio_metrics["source_version"],
        ],
        vendor_versions=[
            *macro_inputs["vendor_versions"],
            *yield_inputs["vendor_versions"],
        ],
        upstream_rule_versions=[
            *macro_inputs["rule_versions"],
            *yield_inputs["rule_versions"],
            portfolio_metrics["rule_version"],
        ],
    )


def _load_landed_equity_research_signals(
    *,
    duckdb_path: str,
    report_date: date,
    macro_latest: dict[str, tuple[date, float]],
) -> tuple[EquityBondSpreadSignal | None, MegaCapEquitySignal | None, list[str]]:
    repo = MacroBondLinkageRepository(duckdb_path, guard_path_exists=True)
    rows, error_warning = repo.fetch_equity_axis_latest_rows(report_date)
    if error_warning is not None:
        return None, None, [error_warning]
    if not rows:
        return None, None, []

    latest: dict[str, tuple[date, float]] = {}
    for series_id, trade_date_value, value_numeric in rows:
        point_date = _coerce_date(trade_date_value)
        if point_date is None:
            continue
        latest[str(series_id)] = (point_date, float(value_numeric))

    cn10y = _latest_macro_value(macro_latest, ["E1000180", "EMM00166466"]) or latest.get("E1000180") or latest.get(
        "EMM00166466"
    )
    index_close = latest.get("CA.CSI300")
    index_pct_change = latest.get("CA.CSI300_PCT_CHG")
    index_pe = latest.get("CA.CSI300_PE")
    equity_signal = None
    if cn10y is not None and index_close is not None and index_pe is not None and index_pe[1] > 0:
        earnings_yield_pct = 100.0 / index_pe[1]
        bond_yield_pct = float(cn10y[1])
        equity_signal = EquityBondSpreadSignal(
            trade_date=index_pe[0],
            index_code="000300.SH",
            index_close=index_close[1],
            index_pct_change=None if index_pct_change is None else index_pct_change[1],
            pe=index_pe[1],
            earnings_yield_pct=earnings_yield_pct,
            bond_yield_pct=bond_yield_pct,
            spread_pct=earnings_yield_pct - bond_yield_pct,
        )

    top10_weight = latest.get("CA.MEGA_CAP_WEIGHT")
    top5_weight = latest.get("CA.MEGA_CAP_TOP5_WEIGHT")
    mega_cap_signal = None
    if top10_weight is not None and top5_weight is not None:
        mega_cap_signal = MegaCapEquitySignal(
            weight_trade_date=max(top10_weight[0], top5_weight[0]),
            index_code="000300.SH",
            top10_weight_sum=top10_weight[1],
            top5_weight_sum=top5_weight[1],
            leading_constituents=[],
            index_pct_change=None if index_pct_change is None else index_pct_change[1],
        )

    return equity_signal, mega_cap_signal, []


def _latest_macro_value(
    macro_latest: dict[str, tuple[date, float]],
    series_ids: list[str],
) -> tuple[date, float] | None:
    for series_id in series_ids:
        value = macro_latest.get(series_id)
        if value is not None:
            return value
    return None


def _load_macro_inputs(
    repo: MacroBondLinkageRepository,
    report_date: date,
    *,
    conn: Any,
) -> dict[str, Any]:
    return repo.load_macro_inputs(report_date, conn=conn)


def _load_yield_inputs(
    repo: MacroBondLinkageRepository,
    report_date: date,
    *,
    conn: Any,
) -> dict[str, Any]:
    return repo.load_yield_inputs(report_date, conn=conn)


def _load_portfolio_metrics(
    repo: MacroBondLinkageRepository,
    report_date: date,
    *,
    conn: Any,
) -> dict[str, Any]:
    return repo.load_portfolio_metrics(report_date, conn=conn)


def _empty_method_variants() -> MacroBondLinkageMethodVariants:
    return MacroBondLinkageMethodVariants(
        conservative=MacroBondLinkageMethodVariant(
            method_meta=MacroBondLinkageMethodMeta(variant="conservative"),
            top_correlations=[],
        ),
        market_timing=MacroBondLinkageMethodVariant(
            method_meta=MacroBondLinkageMethodMeta(variant="market_timing"),
            top_correlations=[],
        ),
    )


def _ranked_correlation_payloads(
    correlations: list[MacroBondCorrelation],
    series_name_map: dict[str, str],
    *,
    alignment_mode: Literal["conservative", "market_timing"],
) -> list[dict[str, Any]]:
    rows = [
        _build_correlation_payload(
            correlation,
            series_name_map,
            alignment_mode=alignment_mode,
        )
        for correlation in correlations
    ]
    rows.sort(key=_correlation_strength, reverse=True)
    return rows[:TOP_CORRELATION_LIMIT]


def _build_response_envelope(
    *,
    report_date: date,
    computed_at: str,
    environment_score: dict[str, Any],
    portfolio_impact: dict[str, Any],
    top_correlations: list[dict[str, Any]],
    method_variants: MacroBondLinkageMethodVariants,
    research_views: list[dict[str, Any]],
    transmission_axes: list[dict[str, Any]],
    warnings: list[str],
    source_versions: list[str],
    vendor_versions: list[str],
    upstream_rule_versions: list[str],
) -> dict[str, object]:
    payload = MacroBondLinkageResponse(
        report_date=report_date,
        environment_score=environment_score,
        portfolio_impact=portfolio_impact,
        top_correlations=top_correlations,
        method_variants=method_variants,
        research_views=research_views,
        transmission_axes=transmission_axes,
        warnings=warnings,
        computed_at=computed_at,
    )
    meta = build_analytical_result_meta(
        trace_id=_trace_id(),
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=_aggregate_lineage(source_versions, EMPTY_SOURCE_VERSION),
        rule_version=_aggregate_lineage([RULE_VERSION, *upstream_rule_versions], RULE_VERSION),
        vendor_version=_aggregate_lineage(vendor_versions, "vv_none"),
    ).model_copy(
        update={
            "quality_flag": "warning" if warnings else "ok",
            "vendor_status": "vendor_unavailable" if not environment_score and not top_correlations else "ok",
            "fallback_mode": "none",
        }
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _macro_context_data_state(
    *,
    environment_score: dict[str, object],
    warnings: list[str],
    quality_flag: str,
    vendor_status: str,
) -> str:
    if not environment_score:
        return "no_data"
    if quality_flag == "stale":
        return "stale"
    if warnings or quality_flag != "ok" or vendor_status != "ok":
        return "degraded"
    return "ready"


def _macro_context_coverage_ratio(evidence_rows: int) -> float:
    return round(min(1.0, max(0.0, evidence_rows / MACRO_CONTEXT_MIN_EVIDENCE_ROWS)), 4)


def _macro_context_confidence_score(
    *,
    coverage_ratio: float,
    freshness_score: float,
    data_state: str,
) -> float:
    state_score = {"ready": 1.0, "degraded": 0.6, "stale": 0.4}.get(data_state, 0.0)
    return round((coverage_ratio + freshness_score + state_score) / 3, 4)


def _macro_context_readiness_reasons(
    *,
    environment_score: dict[str, object],
    warnings: list[str],
    quality_flag: str,
    vendor_status: str,
    coverage_ratio: float,
) -> list[str]:
    reasons: list[str] = []
    if not environment_score:
        reasons.append("MACRO_SCORE_MISSING")
    if coverage_ratio < 1.0:
        reasons.append("MACRO_COVERAGE_INSUFFICIENT")
    if quality_flag != "ok":
        reasons.append(f"MACRO_QUALITY_{quality_flag.upper()}")
    if vendor_status != "ok":
        reasons.append(f"MACRO_VENDOR_{vendor_status.upper()}")
    if warnings:
        reasons.append("MACRO_WARNINGS_PRESENT")
    return _dedupe_preserve_order(reasons)


def _macro_context_id(payload: dict[str, object]) -> str:
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"macroctx_{digest}"


def _aggregate_lineage(values: list[str], empty_value: str) -> str:
    filtered = sorted({str(value).strip() for value in values if str(value).strip()})
    if not filtered:
        return empty_value
    if len(filtered) == 1:
        return filtered[0]
    return "__".join(filtered)


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(parsed, 0)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item or "").strip())]


def _safe_optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _meta_source_version(meta: dict[str, object]) -> object:
    source = _mapping(meta.get("source"))
    return meta.get("source_version") or source.get("source_version") or source.get("version")


def _meta_quality_flag(meta: dict[str, object]) -> object:
    source = _mapping(meta.get("source"))
    return meta.get("quality_flag") or source.get("quality_flag") or source.get("status")


def _meta_vendor_version(meta: dict[str, object]) -> object:
    vendor = _mapping(meta.get("vendor"))
    return meta.get("vendor_version") or vendor.get("vendor_version") or vendor.get("version")


def _meta_vendor_status(meta: dict[str, object]) -> object:
    vendor = _mapping(meta.get("vendor"))
    return meta.get("vendor_status") or vendor.get("vendor_status") or vendor.get("status")


def _meta_fallback_mode(meta: dict[str, object]) -> object:
    source = _mapping(meta.get("source"))
    return meta.get("fallback_mode") or source.get("fallback_mode")


def _meta_evidence_rows(meta: dict[str, object]) -> object:
    evidence = _mapping(meta.get("evidence"))
    return meta.get("evidence_rows") or evidence.get("evidence_rows") or evidence.get("rows")


def _coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(cast(Any, value)))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _build_correlation_payload(
    correlation: MacroBondCorrelation,
    series_name_map: dict[str, str],
    *,
    alignment_mode: Literal["conservative", "market_timing"],
) -> dict[str, Any]:
    target_family, target_tenor = _split_target_identity(correlation.target_yield)
    return _json_safe(
        {
            "series_id": correlation.series_id,
            "series_name": series_name_map.get(correlation.series_id, correlation.series_name),
            "target_yield": correlation.target_yield,
            "target_family": target_family,
            "target_tenor": target_tenor,
            "correlation_3m": correlation.correlation_3m,
            "correlation_6m": correlation.correlation_6m,
            "correlation_1y": correlation.correlation_1y,
            "lead_lag_days": correlation.lead_lag_days,
            "direction": correlation.direction,
            "alignment_mode": alignment_mode,
            "sample_size": correlation.sample_size,
            "winsorized": correlation.winsorized,
            "zscore_applied": correlation.zscore_applied,
            "lead_lag_confidence": correlation.lead_lag_confidence,
            "effective_observation_span_days": correlation.effective_observation_span_days,
        }
    )


def _split_target_identity(target_yield: str) -> tuple[str, str | None]:
    family, separator, tenor = str(target_yield).rpartition("_")
    if not separator:
        return str(target_yield), None
    return family, tenor or None


def _correlation_strength(correlation: dict[str, Any]) -> float:
    candidates = [
        correlation.get("correlation_1y"),
        correlation.get("correlation_6m"),
        correlation.get("correlation_3m"),
    ]
    strengths = [abs(float(value)) for value in candidates if value is not None]
    return max(strengths, default=0.0)
