from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
import uuid

from backend.app.core_finance.macro_bond_linkage import (
    MacroBondCorrelation,
    compute_macro_bond_correlations,
    compute_macro_environment_score,
    estimate_macro_impact_on_portfolio,
)
from backend.app.governance.research_runs import (
    build_research_run_manifest,
    record_research_run,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
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

RULE_VERSION = "rv_macro_bond_linkage_v1"
CACHE_VERSION = "cv_macro_bond_linkage_v1"
RESULT_KIND = "macro_bond_linkage.analysis"
EMPTY_SOURCE_VERSION = "sv_macro_bond_linkage_empty"
LOOKBACK_DAYS = 365
MIN_TRADE_DATES = 30
TOP_CORRELATION_LIMIT = 10


def get_macro_bond_linkage(report_date: date) -> dict[str, object]:
    settings = get_settings()
    computed_at = datetime.now(timezone.utc).isoformat()
    warnings: list[str] = []
    loaded_inputs = MacroBondLinkageRepository(str(settings.duckdb_path)).load_analysis_inputs(
        report_date=report_date,
        lookback_days=LOOKBACK_DAYS,
        empty_source_version=EMPTY_SOURCE_VERSION,
    )
    if loaded_inputs is None:
        warnings.append("DuckDB 只读连接不可用，暂时无法生成宏观-债市联动分析。")
        return _build_response_envelope(
            report_date=report_date,
            computed_at=computed_at,
            environment_score={},
            portfolio_impact={},
            top_correlations=[],
            method_variants=_empty_method_variants(),
            warnings=warnings,
            source_versions=[EMPTY_SOURCE_VERSION],
            vendor_versions=["vv_none"],
            upstream_rule_versions=[],
        )

    macro_inputs, yield_inputs, portfolio_metrics = loaded_inputs
    warnings.extend(portfolio_metrics["warnings"])

    if macro_inputs["trade_date_count"] < MIN_TRADE_DATES:
        warnings.append(
            "fact_choice_macro_daily 数据点不足（少于 30 个交易日），暂不生成宏观-债市联动分析。"
        )
        return _build_response_envelope(
            report_date=report_date,
            computed_at=computed_at,
            environment_score={},
            portfolio_impact={},
            top_correlations=[],
            method_variants=_empty_method_variants(),
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
        environment_score_payload = _json_safe(environment_score)
        portfolio_impact_payload = _json_safe(
            estimate_macro_impact_on_portfolio(
                macro_environment=environment_score,
                portfolio_dv01=portfolio_metrics["portfolio_dv01"],
                portfolio_cs01=portfolio_metrics["portfolio_cs01"],
                portfolio_market_value=portfolio_metrics["portfolio_market_value"],
            )
        )

    return _build_response_envelope(
        report_date=report_date,
        computed_at=computed_at,
        environment_score=environment_score_payload,
        portfolio_impact=portfolio_impact_payload,
        top_correlations=top_correlations,
        method_variants=method_variants,
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
    envelope = build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )
    _record_research_run_manifest(report_date=report_date, envelope=envelope)
    return envelope


def _record_research_run_manifest(*, report_date: date, envelope: dict[str, object]) -> None:
    result_meta = dict(envelope.get("result_meta") or {})
    settings = get_settings()
    manifest = build_research_run_manifest(
        run_kind="analysis",
        source_version=str(result_meta.get("source_version") or EMPTY_SOURCE_VERSION),
        vendor_version=str(result_meta.get("vendor_version") or "vv_none"),
        rule_version=str(result_meta.get("rule_version") or RULE_VERSION),
        parameters={
            "lookback_days": LOOKBACK_DAYS,
            "min_trade_dates": MIN_TRADE_DATES,
            "top_correlation_limit": TOP_CORRELATION_LIMIT,
            "alignment_variants": ["conservative", "market_timing"],
        },
        window={
            "start_date": (report_date - timedelta(days=LOOKBACK_DAYS + 30)).isoformat(),
            "end_date": report_date.isoformat(),
            "as_of_date": report_date.isoformat(),
        },
        universe={
            "macro_table": "fact_choice_macro_daily",
            "curve_table": "fact_formal_yield_curve_daily",
            "risk_table": "fact_formal_risk_tensor_daily",
        },
        code_ref="backend.app.services.macro_bond_linkage_service:get_macro_bond_linkage",
    )
    record_research_run(
        repo=GovernanceRepository(base_dir=settings.governance_path),
        manifest=manifest,
    )


def _aggregate_lineage(values: list[str], empty_value: str) -> str:
    filtered = sorted({str(value).strip() for value in values if str(value).strip()})
    if not filtered:
        return empty_value
    if len(filtered) == 1:
        return filtered[0]
    return "__".join(filtered)


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
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
