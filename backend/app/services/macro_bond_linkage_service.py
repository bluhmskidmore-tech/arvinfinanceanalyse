from __future__ import annotations

import os
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

import duckdb
from backend.app.core_finance.macro_bond_linkage import (
    EquityBondSpreadSignal,
    MacroBondCorrelation,
    MegaCapEquitySignal,
    build_macro_bond_research_output,
    compute_macro_bond_correlations,
    compute_macro_environment_score,
    estimate_macro_impact_on_portfolio,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
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
    computed_at = datetime.now(UTC).isoformat()
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
            research_views=[],
            transmission_axes=[],
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
        environment_score_payload = _json_safe(environment_score)
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
        if _tushare_research_axes_enabled():
            equity_bond_signal, mega_cap_signal, tushare_warnings = _load_tushare_equity_research_signals(
                report_date=report_date,
                macro_latest=macro_inputs["latest"],
            )
            warnings.extend(tushare_warnings)
        research_view_rows, transmission_axis_rows = build_macro_bond_research_output(
            environment_score,
            conservative_corrs,
            equity_bond_spread_signal=equity_bond_signal,
            mega_cap_equity_signal=mega_cap_signal,
        )
        research_views = _json_safe(research_view_rows)
        transmission_axes = _json_safe(transmission_axis_rows)

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


def _tushare_research_axes_enabled() -> bool:
    explicit = str(os.getenv("MOSS_ENABLE_TUSHARE_RESEARCH_AXES", "") or "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _latest_macro_value(
    macro_latest: dict[str, tuple[date, float]],
    series_ids: list[str],
) -> tuple[date, float] | None:
    for series_id in series_ids:
        value = macro_latest.get(series_id)
        if value is not None:
            return value
    return None


def _load_tushare_equity_research_signals(
    *,
    report_date: date,
    macro_latest: dict[str, tuple[date, float]],
) -> tuple[EquityBondSpreadSignal | None, MegaCapEquitySignal | None, list[str]]:
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        return None, None, ["Tushare token missing; equity research axes remain pending."]
    try:
        ts = import_tushare_pro()
    except RuntimeError as exc:
        return None, None, [f"Tushare import failed: {exc}"]

    cn10y = _latest_macro_value(macro_latest, ["E1000180", "EMM00166466"])
    if cn10y is None:
        return None, None, ["CN 10Y macro anchor missing; unable to build equity-bond spread axis."]

    pro = ts.pro_api(token)
    daily_start = (report_date - timedelta(days=35)).strftime("%Y%m%d")
    weight_start = (report_date - timedelta(days=90)).strftime("%Y%m%d")
    report_date_str = report_date.strftime("%Y%m%d")
    warnings: list[str] = []

    try:
        index_daily = pro.index_daily(ts_code="000300.SH", start_date=daily_start, end_date=report_date_str)
        index_dailybasic = pro.index_dailybasic(ts_code="000300.SH", start_date=daily_start, end_date=report_date_str)
        index_weight = pro.index_weight(index_code="000300.SH", start_date=weight_start, end_date=report_date_str)
    except Exception as exc:
        return None, None, [f"Tushare equity fetch failed: {exc}"]

    daily_row = None if index_daily is None or len(index_daily) == 0 else index_daily.sort_values("trade_date").iloc[-1]
    basic_row = None if index_dailybasic is None or len(index_dailybasic) == 0 else index_dailybasic.sort_values("trade_date").iloc[-1]
    equity_signal = None
    index_pct_change = None
    if daily_row is not None:
        index_pct_change = _coerce_float(daily_row.get("pct_chg"))
    if daily_row is not None and basic_row is not None:
        pe = _coerce_float(basic_row.get("pe"))
        close = _coerce_float(daily_row.get("close"))
        if pe and pe > 0 and close is not None:
            earnings_yield_pct = 100.0 / pe
            bond_yield_pct = float(cn10y[1])
            equity_signal = EquityBondSpreadSignal(
                trade_date=_parse_yyyymmdd(str(daily_row.get("trade_date"))),
                index_code="000300.SH",
                index_close=close,
                index_pct_change=index_pct_change,
                pe=pe,
                earnings_yield_pct=earnings_yield_pct,
                bond_yield_pct=bond_yield_pct,
                spread_pct=earnings_yield_pct - bond_yield_pct,
            )
        else:
            warnings.append("Tushare index_dailybasic missing usable PE; equity-bond spread axis remains pending.")

    mega_cap_signal = None
    if index_weight is not None and len(index_weight) > 0:
        latest_weight_date = sorted(index_weight["trade_date"].unique())[-1]
        latest_weight_df = index_weight[index_weight["trade_date"] == latest_weight_date].sort_values("weight", ascending=False)
        if len(latest_weight_df) > 0:
            mega_cap_signal = MegaCapEquitySignal(
                weight_trade_date=_parse_yyyymmdd(str(latest_weight_date)),
                index_code="000300.SH",
                top10_weight_sum=float(latest_weight_df.head(10)["weight"].sum()),
                top5_weight_sum=float(latest_weight_df.head(5)["weight"].sum()),
                leading_constituents=[str(code) for code in latest_weight_df.head(5)["con_code"].tolist()],
                index_pct_change=index_pct_change,
            )
        else:
            warnings.append("Tushare index_weight returned no usable latest rows; mega-cap axis remains pending.")

    return equity_signal, mega_cap_signal, warnings


def _parse_yyyymmdd(raw: str) -> date:
    text = str(raw or "").strip()
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return date.fromisoformat(text)


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(cast(Any, value))
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric


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
        if row is None:
            row = (Decimal("0"), Decimal("0"), Decimal("0"), EMPTY_SOURCE_VERSION, "")
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
