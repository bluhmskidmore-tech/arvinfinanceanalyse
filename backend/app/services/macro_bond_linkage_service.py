from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
import uuid

import duckdb

from backend.app.core_finance.macro_bond_linkage import (
    MacroBondCorrelation,
    compute_macro_bond_correlations,
    compute_macro_environment_score,
    estimate_macro_impact_on_portfolio,
)
from backend.app.governance.settings import get_settings
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
    duckdb_path = str(settings.duckdb_path)
    conn = _connect_read_only(duckdb_path)
    if conn is None:
        warnings.append("DuckDB 只读连接不可用，暂无法生成宏观-债市联动分析。")
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

    try:
        macro_inputs = _load_macro_inputs(conn, report_date)
        yield_inputs = _load_yield_inputs(conn, report_date)
        portfolio_metrics = _load_portfolio_metrics(conn, report_date)
    finally:
        conn.close()

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


def _load_macro_inputs(
    conn: duckdb.DuckDBPyConnection,
    report_date: date,
) -> dict[str, Any]:
    if not _relation_exists(conn, "fact_choice_macro_daily"):
        return {
            "series": {},
            "latest": {},
            "series_name_map": {},
            "trade_date_count": 0,
            "source_versions": [EMPTY_SOURCE_VERSION],
            "vendor_versions": [],
            "rule_versions": [],
        }

    start_date = report_date - timedelta(days=LOOKBACK_DAYS + 30)
    rows = conn.execute(
        """
        select
          series_id,
          series_name,
          cast(trade_date as date) as trade_date,
          cast(value_numeric as double) as value_numeric,
          coalesce(source_version, '') as source_version,
          coalesce(vendor_version, '') as vendor_version,
          coalesce(rule_version, '') as rule_version
        from fact_choice_macro_daily
        where cast(trade_date as date) <= ?
          and cast(trade_date as date) >= ?
          and value_numeric is not null
        order by series_id, cast(trade_date as date)
        """,
        [report_date.isoformat(), start_date.isoformat()],
    ).fetchall()

    series: dict[str, list[tuple[date, float]]] = {}
    latest: dict[str, tuple[date, float]] = {}
    series_name_map: dict[str, str] = {}
    trade_dates: set[date] = set()
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    rule_versions: list[str] = []

    for series_id, series_name, trade_date_value, value_numeric, source_version, vendor_version, rule_version in rows:
        series_id_text = str(series_id)
        point_date = _coerce_date(trade_date_value)
        if point_date is None:
            continue
        value = float(value_numeric)
        series.setdefault(series_id_text, []).append((point_date, value))
        latest[series_id_text] = (point_date, value)
        series_name_map[series_id_text] = str(series_name or series_id_text)
        trade_dates.add(point_date)
        source_versions.append(str(source_version))
        vendor_versions.append(str(vendor_version))
        rule_versions.append(str(rule_version))

    return {
        "series": series,
        "latest": latest,
        "series_name_map": series_name_map,
        "trade_date_count": len(trade_dates),
        "source_versions": _non_empty_values(source_versions),
        "vendor_versions": _non_empty_values(vendor_versions),
        "rule_versions": _non_empty_values(rule_versions),
    }


def _load_yield_inputs(
    conn: duckdb.DuckDBPyConnection,
    report_date: date,
) -> dict[str, Any]:
    if not _relation_exists(conn, "fact_formal_yield_curve_daily"):
        return {
            "series": {},
            "source_versions": [],
            "vendor_versions": [],
            "rule_versions": [],
        }

    start_date = report_date - timedelta(days=LOOKBACK_DAYS + 30)
    rows = conn.execute(
        """
        select
          cast(trade_date as date) as trade_date,
          curve_type,
          tenor,
          cast(rate_pct as double) as rate_pct,
          coalesce(vendor_version, '') as vendor_version,
          coalesce(source_version, '') as source_version,
          coalesce(rule_version, '') as rule_version
        from fact_formal_yield_curve_daily
        where cast(trade_date as date) <= ?
          and cast(trade_date as date) >= ?
          and rate_pct is not null
        order by cast(trade_date as date), curve_type, tenor
        """,
        [report_date.isoformat(), start_date.isoformat()],
    ).fetchall()

    series: dict[str, list[tuple[date, float]]] = {}
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    rule_versions: list[str] = []
    daily_points: dict[tuple[date, str], dict[str, float]] = {}

    for trade_date_value, curve_type, tenor, rate_pct, vendor_version, source_version, rule_version in rows:
        point_date = _coerce_date(trade_date_value)
        if point_date is None:
            continue
        key = f"{curve_type}_{tenor}"
        series.setdefault(key, []).append((point_date, float(rate_pct)))
        daily_points.setdefault((point_date, str(tenor)), {})[str(curve_type)] = float(rate_pct)
        source_versions.append(str(source_version))
        vendor_versions.append(str(vendor_version))
        rule_versions.append(str(rule_version))

    for (trade_date_value, tenor), point_map in daily_points.items():
        if "aaa_credit" in point_map and "treasury" in point_map:
            spread_key = f"credit_spread_{tenor}"
            spread_value = point_map["aaa_credit"] - point_map["treasury"]
            series.setdefault(spread_key, []).append((trade_date_value, spread_value))

    return {
        "series": series,
        "source_versions": _non_empty_values(source_versions),
        "vendor_versions": _non_empty_values(vendor_versions),
        "rule_versions": _non_empty_values(rule_versions),
    }


def _load_portfolio_metrics(
    conn: duckdb.DuckDBPyConnection,
    report_date: date,
) -> dict[str, Any]:
    warnings: list[str] = []
    if _relation_exists(conn, "fact_formal_risk_tensor_daily"):
        row = conn.execute(
            """
            select
              cast(portfolio_dv01 as decimal(24, 8)) as portfolio_dv01,
              cast(cs01 as decimal(24, 8)) as cs01,
              cast(total_market_value as decimal(24, 8)) as total_market_value,
              coalesce(source_version, '') as source_version,
              coalesce(rule_version, '') as rule_version
            from fact_formal_risk_tensor_daily
            where report_date = ?
            limit 1
            """,
            [report_date.isoformat()],
        ).fetchone()
        if row is not None:
            return {
                "portfolio_dv01": _coerce_decimal(row[0]),
                "portfolio_cs01": _coerce_decimal(row[1]),
                "portfolio_market_value": _coerce_decimal(row[2]),
                "source_version": str(row[3] or EMPTY_SOURCE_VERSION),
                "rule_version": str(row[4] or ""),
                "warnings": warnings,
            }

    if _relation_exists(conn, "fact_formal_bond_analytics_daily"):
        row = conn.execute(
            """
            select
              cast(coalesce(sum(dv01), 0) as decimal(24, 8)) as portfolio_dv01,
              cast(coalesce(sum(case when is_credit then spread_dv01 else 0 end), 0) as decimal(24, 8)) as portfolio_cs01,
              cast(coalesce(sum(market_value), 0) as decimal(24, 8)) as portfolio_market_value,
              coalesce(string_agg(distinct source_version, '__'), '') as source_version,
              coalesce(string_agg(distinct rule_version, '__'), '') as rule_version
            from fact_formal_bond_analytics_daily
            where report_date = ?
            """,
            [report_date.isoformat()],
        ).fetchone()
        warnings.append("风险张量缺失，组合 DV01/CS01 已回退到 bond analytics 聚合结果。")
        return {
            "portfolio_dv01": _coerce_decimal(row[0]),
            "portfolio_cs01": _coerce_decimal(row[1]),
            "portfolio_market_value": _coerce_decimal(row[2]),
            "source_version": str(row[3] or EMPTY_SOURCE_VERSION),
            "rule_version": str(row[4] or ""),
            "warnings": warnings,
        }

    warnings.append("组合 DV01/CS01 不可用，组合冲击估算将按 0 返回。")
    return {
        "portfolio_dv01": Decimal("0"),
        "portfolio_cs01": Decimal("0"),
        "portfolio_market_value": Decimal("0"),
        "source_version": EMPTY_SOURCE_VERSION,
        "rule_version": "",
        "warnings": warnings,
    }


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
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _connect_read_only(path: str) -> duckdb.DuckDBPyConnection | None:
    duckdb_file = Path(path)
    if not duckdb_file.exists():
        return None
    try:
        return duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return None


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        union all
        select 1
        from information_schema.views
        where table_name = ?
        limit 1
        """,
        [relation_name, relation_name],
    ).fetchone()
    return row is not None


def _aggregate_lineage(values: list[str], empty_value: str) -> str:
    filtered = sorted({str(value).strip() for value in values if str(value).strip()})
    if not filtered:
        return empty_value
    if len(filtered) == 1:
        return filtered[0]
    return "__".join(filtered)


def _non_empty_values(values: list[str]) -> list[str]:
    return [value for value in values if str(value).strip()]


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _coerce_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))


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
