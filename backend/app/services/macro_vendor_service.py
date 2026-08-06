from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
from backend.app.core_finance.fx_rates import get_usd_cny_rate
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import (
    RULE_VERSION as CFFEX_MEMBER_RANK_RULE_VERSION,
)
from backend.app.repositories.cffex_member_rank_repo import (
    TABLE_NAME as CFFEX_MEMBER_RANK_TABLE,
)
from backend.app.repositories.cffex_member_rank_repo import (
    VIEW_NAME as CFFEX_MEMBER_RANK_VIEW,
)
from backend.app.repositories.cffex_member_rank_repo import (
    normalize_cffex_contract,
    normalize_trade_date,
)
from backend.app.repositories.choice_fx_catalog import (
    classify_fx_series_group,
    discover_formal_fx_candidates,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.macro_vendor import (
    ChoiceMacroLatestPayload,
    ChoiceMacroLatestPoint,
    ChoiceMacroRecentPoint,
    ChoiceMacroRefreshTier,
    FxAnalyticalGroup,
    FxAnalyticalPayload,
    FxAnalyticalSeriesPoint,
    FxFormalStatusPayload,
    FxFormalStatusRow,
    MacroVendorPayload,
    MacroVendorSeries,
)
from backend.app.services import market_data_ncd_proxy_service as ncd_proxy_service
from backend.app.services.formal_result_runtime import build_result_envelope

RULE_VERSION = "rv_phase1_macro_vendor_v1"
CACHE_VERSION = "cv_phase1_macro_vendor_v1"
LIVE_RULE_VERSION = "rv_choice_macro_thin_slice_v1"
LIVE_CACHE_VERSION = "cv_choice_macro_thin_slice_v1"
CHOICE_MACRO_REFRESH_TIERS = {"stable", "fallback", "isolated"}
CHOICE_MACRO_FETCH_MODES = {"date_slice", "latest"}
CHOICE_MACRO_FETCH_GRANULARITIES = {"batch", "single"}
CHOICE_MACRO_REFRESH_JOB_NAME = "choice_macro_refresh"
CHOICE_MACRO_REFRESH_CACHE_KEY = "choice_macro.latest"


def load_macro_vendor_payload(duckdb_path: str) -> MacroVendorPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return MacroVendorPayload(series=[])

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return MacroVendorPayload(series=[])

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "phase1_macro_vendor_catalog" not in tables:
            return MacroVendorPayload(series=[])

        available_columns = {
            str(row[1])
            for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
        }
        select_columns = [
            "series_id",
            "series_name",
            "vendor_name",
            "vendor_version",
            "frequency",
            "unit",
            _catalog_column_expr("theme", available_columns, "NULL"),
            _catalog_column_expr("tags_json", available_columns, "NULL"),
            _catalog_column_expr("refresh_tier", available_columns, "NULL"),
            _catalog_column_expr("fetch_mode", available_columns, "NULL"),
            _catalog_column_expr("fetch_granularity", available_columns, "NULL"),
            _catalog_column_expr("policy_note", available_columns, "NULL"),
        ]
        rows = conn.execute(
            f"""
            select
              {", ".join(select_columns)}
            from phase1_macro_vendor_catalog
            order by vendor_name, series_id
            """
        ).fetchall()
        category_by_series = _load_market_data_category_map(conn, tables)
    except duckdb.Error:
        return MacroVendorPayload(series=[])
    finally:
        conn.close()

    series: list[MacroVendorSeries] = []
    for (
        series_id,
        series_name,
        vendor_name,
        vendor_version,
        frequency,
        unit,
        theme,
        tags_json,
        refresh_tier,
        fetch_mode,
        fetch_granularity,
        policy_note,
    ) in rows:
        category = category_by_series.get(str(series_id), {})
        series.append(
            MacroVendorSeries(
                series_id=str(series_id),
                series_name=str(series_name),
                vendor_name=str(vendor_name),
                vendor_version=str(vendor_version),
                frequency=str(frequency),
                unit=str(unit),
                theme=_as_optional_string(theme) or "unknown",
                tags=_parse_string_list_json(tags_json),
                refresh_tier=_sanitize_choice_macro_refresh_tier(
                    category.get("refresh_tier") or refresh_tier
                ),
                fetch_mode=_sanitize_choice_macro_fetch_mode(category.get("fetch_mode") or fetch_mode),
                fetch_granularity=_sanitize_choice_macro_fetch_granularity(
                    category.get("fetch_granularity") or fetch_granularity
                ),
                policy_note=_as_optional_string(category.get("policy_note") or policy_note),
            )
        )
    return MacroVendorPayload(series=series)


def macro_vendor_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_macro_vendor_payload(duckdb_path)
    source_version = _load_macro_vendor_source_version(
        duckdb_path,
        series_ids=[item.series_id for item in payload.series],
    )
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in payload.series],
        empty_value="vv_none",
    )
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_preview_macro_foundation",
        result_kind="preview.macro-foundation",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        quality_flag=_quality_flag_for_presence(payload.series),
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_presence(payload.series),
        fallback_mode="none",
        result_payload=payload.model_dump(mode="json"),
    )


def _load_macro_vendor_source_version(duckdb_path: str, series_ids: list[str]) -> str:
    if not series_ids:
        return "sv_macro_vendor_empty"

    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return "sv_macro_vendor_empty"

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return "sv_macro_vendor_empty"

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_market_snapshot" not in tables:
            return "sv_macro_vendor_empty"

        placeholders = ", ".join(["?"] * len(series_ids))
        rows = conn.execute(
            f"""
            select distinct source_version
            from choice_market_snapshot
            where series_id in ({placeholders})
              and source_version is not null and source_version <> ''
            order by source_version
            """,
            series_ids,
        ).fetchall()
    except duckdb.Error:
        return "sv_macro_vendor_empty"
    finally:
        conn.close()

    return _aggregate_lineage_value(
        [str(row[0]) for row in rows if row and row[0]],
        empty_value="sv_macro_vendor_empty",
    )


def load_choice_macro_latest_payload(
    duckdb_path: str,
    category: ChoiceMacroRefreshTier | None = None,
) -> ChoiceMacroLatestPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return ChoiceMacroLatestPayload(series=[])

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return ChoiceMacroLatestPayload(series=[])

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fact_choice_macro_daily" not in tables:
            return ChoiceMacroLatestPayload(series=[])

        recent_rows = _load_choice_macro_recent_rows(conn, tables)
        catalog_by_series = _load_choice_macro_catalog_map(conn, tables)
    except duckdb.Error:
        return ChoiceMacroLatestPayload(series=[])
    finally:
        conn.close()

    if not recent_rows:
        return ChoiceMacroLatestPayload(series=[])

    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for (
        series_id,
        series_name,
        trade_date,
        value_numeric,
        frequency,
        unit,
        source_version,
        vendor_version,
        quality_flag,
        _rn,
    ) in recent_rows:
        grouped_rows.setdefault(str(series_id), []).append(
            {
                "series_id": str(series_id),
                "series_name": str(series_name),
                "trade_date": str(trade_date),
                "value_numeric": float(value_numeric),
                "frequency": str(frequency),
                "unit": str(unit),
                "source_version": str(source_version),
                "vendor_version": str(vendor_version),
                "quality_flag": str(quality_flag),
            }
        )

    series = []
    for series_id in sorted(grouped_rows):
        rows = grouped_rows[series_id]
        latest = rows[0]
        recent_points = [
            ChoiceMacroRecentPoint(
                trade_date=str(row["trade_date"]),
                value_numeric=float(row["value_numeric"]),
                source_version=str(row["source_version"]),
                vendor_version=str(row["vendor_version"]),
                quality_flag=_normalize_quality_flag(str(row["quality_flag"])),
            )
            for row in rows
        ]
        catalog = catalog_by_series.get(
            series_id,
            {
                "frequency": latest["frequency"],
                "unit": latest["unit"],
                "vendor_name": None,
                "refresh_tier": None,
                "fetch_mode": None,
                "fetch_granularity": None,
                "policy_note": None,
            },
        )
        refresh_tier = _as_optional_string(catalog.get("refresh_tier"))
        effective_category = refresh_tier or "stable"
        if category is not None:
            if effective_category != category:
                continue
        elif refresh_tier == "isolated":
            continue
        latest_change = None
        if len(rows) > 1:
            latest_change = float(latest["value_numeric"]) - float(rows[1]["value_numeric"])

        series.append(
            ChoiceMacroLatestPoint(
                series_id=series_id,
                series_name=str(latest["series_name"]),
                trade_date=str(latest["trade_date"]),
                value_numeric=float(latest["value_numeric"]),
                frequency=str(catalog["frequency"] or latest["frequency"]),
                unit=str(catalog["unit"] or latest["unit"]),
                source_version=str(latest["source_version"]),
                vendor_version=str(latest["vendor_version"]),
                vendor_name=_as_optional_string(catalog.get("vendor_name")),
                refresh_tier=refresh_tier,
                fetch_mode=_as_optional_string(catalog.get("fetch_mode")),
                fetch_granularity=_as_optional_string(catalog.get("fetch_granularity")),
                policy_note=_as_optional_string(catalog.get("policy_note")),
                quality_flag=_normalize_quality_flag(str(latest["quality_flag"])),
                latest_change=latest_change,
                recent_points=recent_points,
            )
        )

    return ChoiceMacroLatestPayload(series=series)


def choice_macro_latest_envelope(
    duckdb_path: str,
    category: ChoiceMacroRefreshTier | None = None,
) -> dict[str, object]:
    payload = load_choice_macro_latest_payload(duckdb_path, category=category)
    quality_flag = _aggregate_quality_flags([item.quality_flag for item in payload.series])
    source_version = _aggregate_lineage_value(
        [item.source_version for item in payload.series],
        empty_value="sv_choice_macro_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in payload.series],
        empty_value="vv_none",
    )
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_choice_macro_latest",
        result_kind="macro.choice.latest",
        cache_version=LIVE_CACHE_VERSION,
        source_version=source_version,
        rule_version=LIVE_RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_macro_latest(payload, quality_flag),
        fallback_mode=_fallback_mode_for_macro_latest(payload, quality_flag),
        result_payload=payload.model_dump(mode="json"),
    )


FORMAL_RATES_RULE_VERSION = "rv_market_data_rates_formal_v1"
FORMAL_RATES_CACHE_VERSION = "cv_market_data_rates_formal_v1"
TUSHARE_SUPPLEMENT_RULE_VERSION = "rv_market_data_tushare_supplement_v1"
TUSHARE_SUPPLEMENT_CACHE_VERSION = "cv_market_data_tushare_supplement_v1"
BOND_FUTURES_RANKINGS_CACHE_VERSION = "cv_market_data_bond_futures_rankings_v1"
COVERAGE_SUMMARY_RULE_VERSION = "rv_market_data_coverage_summary_v1"
COVERAGE_SUMMARY_CACHE_VERSION = "cv_market_data_coverage_summary_v1"

FORMAL_YIELD_CURVE_TABLES = ("fact_formal_yield_curve_daily", "yield_curve_daily")
FORMAL_YIELD_CURVE_SERIES: dict[tuple[str, str], tuple[str, str]] = {
    ("treasury", "1Y"): ("EMM00166458", "China treasury yield 1Y"),
    ("treasury", "2Y"): ("EMM00588704", "China treasury yield 2Y"),
    ("treasury", "3Y"): ("EMM00166460", "China treasury yield 3Y"),
    ("treasury", "5Y"): ("EMM00166462", "China treasury yield 5Y"),
    ("treasury", "7Y"): ("EMM00166464", "China treasury yield 7Y"),
    ("treasury", "10Y"): ("EMM00166466", "China treasury yield 10Y"),
    ("treasury", "20Y"): ("EMM00166468", "China treasury yield 20Y"),
    ("treasury", "30Y"): ("EMM00166469", "China treasury yield 30Y"),
    ("cdb", "1Y"): ("EMM00166494", "China CDB yield 1Y"),
    ("cdb", "2Y"): ("EMM00166495", "China CDB yield 2Y"),
    ("cdb", "3Y"): ("EMM00166496", "China CDB yield 3Y"),
    ("cdb", "5Y"): ("EMM00166498", "China CDB yield 5Y"),
    ("cdb", "10Y"): ("EMM00166502", "China CDB yield 10Y"),
    ("cdb", "20Y"): ("EMM00166504", "China CDB yield 20Y"),
}


def _normalize_formal_rate_unit(unit: str | None) -> str:
    normalized = (unit or "").strip().lower()
    if normalized in {"", "unknown", "pct", "percent"}:
        return "%"
    return unit or "%"


def _latest_point_as_recent(point: ChoiceMacroLatestPoint) -> ChoiceMacroRecentPoint:
    return ChoiceMacroRecentPoint(
        trade_date=point.trade_date,
        value_numeric=point.value_numeric,
        source_version=point.source_version,
        vendor_version=point.vendor_version,
        quality_flag=point.quality_flag,
    )


def _load_formal_yield_curve_points(
    duckdb_path: str,
) -> tuple[list[ChoiceMacroLatestPoint], str | None]:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return [], None

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return [], None

    table_name: str | None = None
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        for candidate in FORMAL_YIELD_CURVE_TABLES:
            if candidate in tables:
                table_name = candidate
                break
        if table_name is None:
            return [], None

        curve_types = sorted({curve_type for curve_type, _tenor in FORMAL_YIELD_CURVE_SERIES})
        tenors = sorted({tenor for _curve_type, tenor in FORMAL_YIELD_CURVE_SERIES})
        curve_placeholders = ", ".join(["?"] * len(curve_types))
        tenor_placeholders = ", ".join(["?"] * len(tenors))
        rows = conn.execute(
            f"""
            with ranked as (
              select
                curve_type,
                tenor,
                cast(trade_date as varchar) as trade_date,
                cast(rate_pct as double) as value_numeric,
                coalesce(vendor_name, '') as vendor_name,
                coalesce(vendor_version, '') as vendor_version,
                coalesce(source_version, '') as source_version,
                row_number() over (
                  partition by curve_type, tenor
                  order by trade_date desc
                ) as rn
              from {table_name}
              where curve_type in ({curve_placeholders})
                and tenor in ({tenor_placeholders})
                and rate_pct is not null
            )
            select
              curve_type,
              tenor,
              trade_date,
              value_numeric,
              vendor_name,
              vendor_version,
              source_version,
              rn
            from ranked
            where rn <= {_CHOICE_MACRO_RECENT_POINT_LIMIT}
            order by curve_type, tenor, rn
            """,
            [*curve_types, *tenors],
        ).fetchall()
    except duckdb.Error:
        return [], None
    finally:
        conn.close()

    grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = {}
    for curve_type, tenor, trade_date, value_numeric, vendor_name, vendor_version, source_version, _rn in rows:
        key = (str(curve_type), str(tenor))
        if key not in FORMAL_YIELD_CURVE_SERIES:
            continue
        grouped_rows.setdefault(key, []).append(
            {
                "trade_date": str(trade_date),
                "value_numeric": float(value_numeric),
                "vendor_name": str(vendor_name or "unknown"),
                "vendor_version": str(vendor_version or "vv_formal_yield_curve_unknown"),
                "source_version": str(source_version or "sv_formal_yield_curve_unknown"),
            }
        )

    points: list[ChoiceMacroLatestPoint] = []
    for key in sorted(grouped_rows):
        series_id, series_name = FORMAL_YIELD_CURVE_SERIES[key]
        curve_rows = sorted(grouped_rows[key], key=lambda row: str(row["trade_date"]), reverse=True)
        latest = curve_rows[0]
        recent_points = [
            ChoiceMacroRecentPoint(
                trade_date=str(row["trade_date"]),
                value_numeric=float(row["value_numeric"]),
                source_version=str(row["source_version"]),
                vendor_version=str(row["vendor_version"]),
                quality_flag="ok",
            )
            for row in curve_rows
        ]
        latest_change = None
        if len(recent_points) > 1:
            latest_change = recent_points[0].value_numeric - recent_points[1].value_numeric
        points.append(
            ChoiceMacroLatestPoint(
                series_id=series_id,
                series_name=series_name,
                trade_date=str(latest["trade_date"]),
                value_numeric=float(latest["value_numeric"]),
                frequency="daily",
                unit="%",
                source_version=str(latest["source_version"]),
                vendor_version=str(latest["vendor_version"]),
                vendor_name=str(latest["vendor_name"] or "unknown"),
                refresh_tier="stable",
                fetch_mode="date_slice",
                fetch_granularity="batch",
                policy_note="Formal yield curve daily materialization.",
                quality_flag="ok",
                latest_change=latest_change,
                recent_points=recent_points,
            )
        )
    return points, table_name


def _merge_formal_yield_curve_history(
    existing: ChoiceMacroLatestPoint,
    formal: ChoiceMacroLatestPoint,
) -> ChoiceMacroLatestPoint:
    latest_source = existing if existing.trade_date >= formal.trade_date else formal
    ordered_sources = [formal, existing] if latest_source is existing else [existing, formal]
    recent_by_date: dict[str, ChoiceMacroRecentPoint] = {}
    for source in ordered_sources:
        for point in source.recent_points:
            recent_by_date[point.trade_date] = point
        recent_by_date[source.trade_date] = _latest_point_as_recent(source)

    recent_points = sorted(
        recent_by_date.values(),
        key=lambda point: point.trade_date,
        reverse=True,
    )[:_CHOICE_MACRO_RECENT_POINT_LIMIT]
    latest_change = latest_source.latest_change
    if len(recent_points) > 1 and recent_points[0].trade_date == latest_source.trade_date:
        latest_change = recent_points[0].value_numeric - recent_points[1].value_numeric

    return latest_source.model_copy(
        update={
            "unit": _normalize_formal_rate_unit(latest_source.unit),
            "latest_change": latest_change,
            "recent_points": recent_points,
        }
    )


def _merge_formal_yield_curve_payload(
    payload: ChoiceMacroLatestPayload,
    formal_points: list[ChoiceMacroLatestPoint],
) -> ChoiceMacroLatestPayload:
    if not formal_points:
        return payload

    points_by_id = {point.series_id: point for point in payload.series}
    for formal in formal_points:
        existing = points_by_id.get(formal.series_id)
        points_by_id[formal.series_id] = (
            _merge_formal_yield_curve_history(existing, formal)
            if existing is not None
            else formal
        )

    return ChoiceMacroLatestPayload(
        series=sorted(points_by_id.values(), key=lambda point: point.series_id)
    )


def choice_macro_formal_envelope(duckdb_path: str) -> dict[str, object]:
    """Formal-basis envelope: only stable-tier series for market-data page."""
    payload = load_choice_macro_latest_payload(duckdb_path, category="stable")
    choice_series_count = len(payload.series)
    formal_points, formal_table = _load_formal_yield_curve_points(duckdb_path)
    payload = _merge_formal_yield_curve_payload(payload, formal_points)
    quality_flag = _aggregate_quality_flags([item.quality_flag for item in payload.series])
    source_versions = [item.source_version for item in payload.series]
    source_versions.extend(item.source_version for item in formal_points)
    vendor_versions = [item.vendor_version for item in payload.series]
    vendor_versions.extend(item.vendor_version for item in formal_points)
    source_version = _aggregate_lineage_value(
        source_versions,
        empty_value="sv_market_data_rates_empty",
    )
    vendor_version = _aggregate_lineage_value(
        vendor_versions,
        empty_value="vv_none",
    )
    tables_used = ["fact_choice_macro_daily"] if choice_series_count else []
    if formal_table and formal_points:
        tables_used.append(formal_table)
    return build_result_envelope(
        basis="formal",
        trace_id="tr_market_data_formal",
        result_kind="market_data.rates",
        cache_version=FORMAL_RATES_CACHE_VERSION,
        source_version=source_version,
        rule_version=FORMAL_RATES_RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_macro_latest(payload, quality_flag),
        fallback_mode=_fallback_mode_for_macro_latest(payload, quality_flag),
        result_payload=payload.model_dump(mode="json"),
        tables_used=tables_used,
        evidence_rows=len(payload.series),
        source_surface="market_data",
    )


def macro_foundation_formal_envelope(duckdb_path: str) -> dict[str, object]:
    """Formal-basis envelope for the macro catalog (stable entries)."""
    payload = load_macro_vendor_payload(duckdb_path)
    stable_payload = MacroVendorPayload(
        series=[item for item in payload.series if item.refresh_tier == "stable"]
    )
    source_version = _load_macro_vendor_source_version(
        duckdb_path,
        series_ids=[item.series_id for item in stable_payload.series],
    )
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in stable_payload.series],
        empty_value="vv_none",
    )
    return build_result_envelope(
        basis="formal",
        trace_id="tr_market_data_catalog_formal",
        result_kind="market_data.catalog",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        quality_flag=_quality_flag_for_presence(stable_payload.series),
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_presence(stable_payload.series),
        fallback_mode="none",
        result_payload=stable_payload.model_dump(mode="json"),
        source_surface="market_data",
    )


def tushare_supplement_envelope(
    duckdb_path: str,
    *,
    money_supply_limit: int = 12,
    eco_cal_limit: int = 30,
) -> dict[str, object]:
    payload, source_versions, vendor_versions, latest_date, warnings, tables_used = _load_tushare_supplement_payload(
        duckdb_path,
        money_supply_limit=money_supply_limit,
        eco_cal_limit=eco_cal_limit,
    )
    row_count = len(payload["money_supply_rows"]) + len(payload["eco_cal_rows"])
    quality_flag = "ok" if row_count > 0 and not warnings else "warning"
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_market_data_tushare_supplement",
        result_kind="market_data.tushare_supplement",
        cache_version=TUSHARE_SUPPLEMENT_CACHE_VERSION,
        source_version=_aggregate_lineage_value(source_versions, empty_value="sv_tushare_supplement_empty"),
        rule_version=TUSHARE_SUPPLEMENT_RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=_aggregate_lineage_value(vendor_versions, empty_value="vv_none"),
        vendor_status="ok" if row_count > 0 else "vendor_unavailable",
        fallback_mode="none",
        result_payload=payload,
        tables_used=tables_used,
        evidence_rows=row_count,
        source_surface="market_data",
        as_of_date=latest_date,
        resolved_report_date=latest_date,
    )


def market_data_bond_futures_rankings_envelope(
    duckdb_path: str,
    *,
    contract: str = "T.CFE",
    trade_date: str | None = None,
    limit: int = 10,
) -> dict[str, object]:
    payload, source_versions, vendor_versions, latest_date, warnings, tables_used = (
        _load_bond_futures_rankings_payload(
            duckdb_path,
            contract=contract,
            trade_date=trade_date,
            limit=limit,
        )
    )
    row_count = len(payload["rows"])
    quality_flag = "ok" if row_count > 0 and not warnings else "warning"
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_market_data_bond_futures_rankings",
        result_kind="market_data.bond_futures_rankings",
        cache_version=BOND_FUTURES_RANKINGS_CACHE_VERSION,
        source_version=_aggregate_lineage_value(source_versions, empty_value="sv_cffex_member_rank_empty"),
        rule_version=CFFEX_MEMBER_RANK_RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=_aggregate_lineage_value(vendor_versions, empty_value="vv_none"),
        vendor_status="ok" if row_count > 0 else "vendor_unavailable",
        fallback_mode="none",
        result_payload=payload,
        filters_applied={
            "contract": payload["contract"],
            "trade_date": payload["requested_trade_date"],
            "limit": max(0, min(int(limit), 100)),
        },
        tables_used=tables_used,
        evidence_rows=row_count,
        source_surface="market_data",
        as_of_date=latest_date,
        resolved_report_date=latest_date,
    )


def market_data_coverage_summary_envelope(duckdb_path: str) -> dict[str, object]:
    formal_rates = choice_macro_formal_envelope(duckdb_path)
    macro_latest = choice_macro_latest_envelope(duckdb_path)
    fx_formal = fx_formal_status_envelope(duckdb_path)
    fx_analytical = fx_analytical_envelope(duckdb_path)
    ncd_proxy = ncd_proxy_service.ncd_funding_proxy_envelope(duckdb_path)
    bond_futures = market_data_bond_futures_rankings_envelope(
        duckdb_path,
        contract="T.CFE",
        limit=10,
    )
    tushare = tushare_supplement_envelope(
        duckdb_path,
        money_supply_limit=120,
        eco_cal_limit=300,
    )

    formal_rate_rows = formal_rates["result"].get("series", [])
    macro_latest_rows = macro_latest["result"].get("series", [])
    fx_formal_result = fx_formal["result"]
    fx_analytical_groups = fx_analytical["result"].get("groups", [])
    fx_analytical_series_count = sum(len(group.get("series", [])) for group in fx_analytical_groups)
    ncd_result = ncd_proxy["result"]
    ncd_rows = ncd_result.get("rows", [])
    ncd_as_of_date = _string_or_none(ncd_result.get("as_of_date"))
    bond_rows = bond_futures["result"].get("rows", [])
    tushare_result = tushare["result"]
    tushare_row_count = len(tushare_result.get("money_supply_rows", [])) + len(
        tushare_result.get("eco_cal_rows", [])
    )

    sections = [
        _coverage_section(
            key="formal_rates",
            label="Formal rates fragment",
            status="ready" if formal_rate_rows else "empty",
            basis="formal",
            formal_use_allowed=True,
            meta=formal_rates["result_meta"],
            series_count=len(formal_rate_rows),
            latest_trade_date=_latest_choice_series_date(formal_rate_rows),
            source_pending=False,
            proxy_only=False,
            message=f"Stable rate series returned by the formal market-data rates fragment: {len(formal_rate_rows)}.",
        ),
        _coverage_section(
            key="macro_latest",
            label="Macro latest observations",
            status="warning" if macro_latest_rows else "empty",
            basis="analytical",
            formal_use_allowed=False,
            meta=macro_latest["result_meta"],
            series_count=len(macro_latest_rows),
            latest_trade_date=_latest_choice_series_date(macro_latest_rows),
            source_pending=False,
            proxy_only=False,
            message="Analytical Choice macro latest snapshot is for observation only.",
        ),
        _coverage_section(
            key="fx_formal",
            label="FX formal status",
            status=_fx_formal_coverage_status(fx_formal_result),
            basis="formal",
            formal_use_allowed=bool(fx_formal["result_meta"].get("formal_use_allowed")),
            meta=fx_formal["result_meta"],
            row_count=int(fx_formal_result.get("materialized_count") or 0),
            series_count=int(fx_formal_result.get("candidate_count") or 0),
            latest_trade_date=_string_or_none(fx_formal_result.get("latest_trade_date")),
            source_pending=False,
            proxy_only=False,
            message="Formal FX candidate and materialization status.",
        ),
        _coverage_section(
            key="fx_analytical",
            label="FX analytical groups",
            status="warning" if fx_analytical_series_count > 0 else "empty",
            basis="analytical",
            formal_use_allowed=False,
            meta=fx_analytical["result_meta"],
            row_count=fx_analytical_series_count,
            group_count=len(fx_analytical_groups),
            latest_trade_date=_latest_fx_group_date(fx_analytical_groups),
            source_pending=False,
            proxy_only=False,
            message="Analytical FX groups remain observation-only.",
        ),
        _coverage_section(
            key="ncd_proxy",
            label="NCD funding proxy",
            status="proxy_only" if ncd_rows else "empty",
            basis="analytical",
            formal_use_allowed=False,
            meta=ncd_proxy["result_meta"],
            row_count=len(ncd_rows) if isinstance(ncd_rows, list) else None,
            latest_trade_date=ncd_as_of_date,
            as_of_date=ncd_as_of_date,
            source_pending=not bool(ncd_rows),
            proxy_only=bool(ncd_rows),
            message=(
                "No NCD funding proxy rows are available; the formal tenor-rating matrix "
                "remains source-pending."
                if not ncd_rows
                else "Proxy-only NCD funding rows reflect the landed Shibor coverage snapshot."
            ),
        ),
        _coverage_section(
            key="bond_futures",
            label="Bond futures rankings",
            status="ready" if bond_rows else "source_pending",
            basis="analytical",
            formal_use_allowed=False,
            meta=bond_futures["result_meta"],
            row_count=len(bond_rows),
            latest_trade_date=_string_or_none(bond_futures["result"].get("as_of_date")),
            source_pending=not bool(bond_rows),
            proxy_only=False,
            message=(
                "CFFEX member-rank rows are available from landed Choice/Tushare data."
                if bond_rows
                else "CFFEX member-rank rows are not available for the requested contract."
            ),
        ),
        _coverage_section(
            key="tushare_supplement",
            label="Tushare supplement",
            status="ready" if tushare_row_count else "source_pending",
            basis="analytical",
            formal_use_allowed=False,
            meta=tushare["result_meta"],
            row_count=tushare_row_count,
            latest_trade_date=_result_meta_date(tushare["result_meta"]),
            source_pending=tushare_row_count == 0,
            proxy_only=False,
            message="Tushare money supply and economic calendar supplement.",
        ),
        _source_pending_coverage_section("cash_bond_trades", "Cash bond trades"),
        _source_pending_coverage_section("credit_trades", "Credit trades"),
    ]
    source_pending_count = sum(1 for section in sections if section["source_pending"])
    proxy_only_count = sum(1 for section in sections if section["proxy_only"])
    analytical_warning_count = sum(
        1
        for section in sections
        if section["basis"] == "analytical"
        and section["status"] in {"warning", "empty", "stale", "deferred"}
        and not section["source_pending"]
    )
    readable_count = sum(
        1
        for section in sections
        if section["status"] not in {"empty", "source_pending"}
    )
    empty_count = sum(1 for section in sections if section["status"] == "empty")
    as_of_date = _latest_coverage_date(sections)
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "read_target": "duckdb",
        "as_of_date": as_of_date,
        "generated_at": generated_at,
        "headline": {
            "readiness_label": (
                f"{readable_count}/{len(sections)} sections readable; "
                f"{source_pending_count} source gaps; {empty_count} empty; "
                f"{proxy_only_count} proxy-only"
            ),
            "readable_count": readable_count,
            "empty_count": empty_count,
            "formal_fragment_ready": bool(formal_rate_rows),
            "formal_use_allowed": False,
            "analytical_warning_count": analytical_warning_count,
            "source_pending_count": source_pending_count,
            "proxy_only_count": proxy_only_count,
        },
        "sections": sections,
        "actions": _coverage_actions(sections),
    }
    source_versions = [
        _meta_text(envelope, "source_version")
        for envelope in (formal_rates, macro_latest, fx_formal, fx_analytical, ncd_proxy, bond_futures, tushare)
    ]
    vendor_versions = [
        _meta_text(envelope, "vendor_version")
        for envelope in (formal_rates, macro_latest, fx_formal, fx_analytical, ncd_proxy, bond_futures, tushare)
    ]
    tables_used: list[str] = []
    for envelope in (formal_rates, macro_latest, fx_formal, fx_analytical, ncd_proxy, bond_futures, tushare):
        tables_used.extend(str(item) for item in envelope.get("result_meta", {}).get("tables_used", []))

    return build_result_envelope(
        basis="analytical",
        trace_id="tr_market_data_coverage_summary",
        result_kind="market_data.coverage_summary",
        cache_version=COVERAGE_SUMMARY_CACHE_VERSION,
        source_version=_aggregate_lineage_value(source_versions, empty_value="sv_market_data_coverage_empty"),
        rule_version=COVERAGE_SUMMARY_RULE_VERSION,
        quality_flag="warning" if source_pending_count or proxy_only_count else "ok",
        vendor_version=_aggregate_lineage_value(vendor_versions, empty_value="vv_none"),
        vendor_status="ok",
        fallback_mode="none",
        result_payload=payload,
        tables_used=sorted(set(tables_used)),
        evidence_rows=sum(_coverage_evidence_count(section) for section in sections),
        source_surface="market_data",
        as_of_date=as_of_date,
        resolved_report_date=as_of_date,
        generated_at=generated_at,
    )


def _load_tushare_supplement_payload(
    duckdb_path: str,
    *,
    money_supply_limit: int,
    eco_cal_limit: int,
) -> tuple[dict[str, object], list[str], list[str], str | None, list[str], list[str]]:
    money_limit = max(0, min(int(money_supply_limit), 120))
    eco_limit = max(0, min(int(eco_cal_limit), 300))
    payload: dict[str, object] = {
        "money_supply_rows": [],
        "money_supply_total_count": 0,
        "money_supply_truncated": False,
        "eco_cal_rows": [],
        "eco_cal_total_count": 0,
        "eco_cal_truncated": False,
        "warnings": [],
    }
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    latest_dates: list[str] = []
    warnings: list[str] = []
    tables_used: list[str] = []

    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        warnings.append("DuckDB file is not available for Tushare supplement.")
        payload["warnings"] = warnings
        return payload, source_versions, vendor_versions, None, warnings, tables_used

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error as exc:
        warnings.append(f"DuckDB read failed for Tushare supplement: {exc}")
        payload["warnings"] = warnings
        return payload, source_versions, vendor_versions, None, warnings, tables_used

    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        (
            money_rows,
            money_source_versions,
            money_vendor_versions,
            money_latest,
            money_tables,
            money_warnings,
            money_total_count,
        ) = _load_tushare_money_supply_rows(conn, tables, limit=money_limit)
        (
            eco_rows,
            eco_source_versions,
            eco_vendor_versions,
            eco_latest,
            eco_tables,
            eco_warnings,
            eco_total_count,
        ) = _load_tushare_eco_calendar_rows(conn, tables, limit=eco_limit)
    finally:
        conn.close()

    payload["money_supply_rows"] = money_rows
    payload["money_supply_total_count"] = money_total_count
    payload["money_supply_truncated"] = money_total_count > len(money_rows)
    payload["eco_cal_rows"] = eco_rows
    payload["eco_cal_total_count"] = eco_total_count
    payload["eco_cal_truncated"] = eco_total_count > len(eco_rows)
    source_versions.extend(money_source_versions)
    source_versions.extend(eco_source_versions)
    vendor_versions.extend(money_vendor_versions)
    vendor_versions.extend(eco_vendor_versions)
    if money_latest:
        latest_dates.append(money_latest)
    if eco_latest:
        latest_dates.append(eco_latest)
    tables_used.extend(money_tables)
    tables_used.extend(eco_tables)
    warnings.extend(money_warnings)
    warnings.extend(eco_warnings)
    payload["warnings"] = warnings
    latest_date = _max_normalized_iso_date(latest_dates)
    return payload, source_versions, vendor_versions, latest_date, warnings, tables_used


def _load_tushare_money_supply_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    *,
    limit: int,
) -> tuple[
    list[dict[str, object]],
    list[str],
    list[str],
    str | None,
    list[str],
    list[str],
    int,
]:
    if "std_tushare_money_supply_monthly" in tables:
        rows, source_versions, vendor_versions, latest, warnings, total_count = (
            _load_tushare_money_supply_table(conn, limit=limit)
        )
        return (
            rows,
            source_versions,
            vendor_versions,
            latest,
            ["std_tushare_money_supply_monthly"],
            warnings,
            total_count,
        )
    if "std_external_macro_daily" in tables:
        rows, source_versions, vendor_versions, latest, warnings, total_count = (
            _load_tushare_money_supply_external_macro(conn, limit=limit)
        )
        if total_count == 0 and not warnings:
            warnings = ["Tushare money supply rows are not materialized."]
        return (
            rows,
            source_versions,
            vendor_versions,
            latest,
            ["std_external_macro_daily"],
            warnings,
            total_count,
        )
    warnings = [] if limit <= 0 else ["Tushare money supply table is not materialized."]
    return [], [], [], None, [], warnings, 0


def _load_tushare_money_supply_table(
    conn: duckdb.DuckDBPyConnection,
    *,
    limit: int,
) -> tuple[list[dict[str, object]], list[str], list[str], str | None, list[str], int]:
    columns = _duckdb_table_columns(conn, "std_tushare_money_supply_monthly")
    select_columns = [
        _column_or_null("month", columns),
        _column_or_null("m0", columns),
        _column_or_null("m0_yoy", columns),
        _column_or_null("m0_mom", columns),
        _column_or_null("m1", columns),
        _column_or_null("m1_yoy", columns),
        _column_or_null("m1_mom", columns),
        _column_or_null("m2", columns),
        _column_or_null("m2_yoy", columns),
        _column_or_null("m2_mom", columns),
        _column_or_null("source_version", columns),
        _column_or_null("vendor_version", columns),
        _column_or_null("created_at", columns),
        _column_or_null("ingest_batch_id", columns),
    ]
    raw_rows = conn.execute(
        f"""
        select {", ".join(select_columns)}
        from std_tushare_money_supply_monthly
        """
    ).fetchall()
    candidates_by_month: dict[str, list[dict[str, object]]] = {}
    for raw in raw_rows:
        month = _normalize_iso_date(raw[0])
        if not month:
            continue
        row = {
            "month": month,
            "m0": _float_or_none(raw[1]),
            "m0_yoy": _float_or_none(raw[2]),
            "m0_mom": _float_or_none(raw[3]),
            "m1": _float_or_none(raw[4]),
            "m1_yoy": _float_or_none(raw[5]),
            "m1_mom": _float_or_none(raw[6]),
            "m2": _float_or_none(raw[7]),
            "m2_yoy": _float_or_none(raw[8]),
            "m2_mom": _float_or_none(raw[9]),
        }
        candidate = {
            "month": month,
            "row": row,
            "source_version": _string_or_none(raw[10]),
            "vendor_version": _string_or_none(raw[11]),
            "lineage_key": (
                _timestamp_sort_key(raw[12]),
                _string_sort_key(raw[13]),
            ),
            "content_key": _stable_tushare_content_key(
                row,
                source_version=raw[10],
                vendor_version=raw[11],
            ),
        }
        candidates_by_month.setdefault(month, []).append(candidate)

    selected: list[dict[str, object]] = []
    warnings: list[str] = []
    for month in sorted(candidates_by_month, reverse=True):
        candidate, warning = _resolve_tushare_candidate(
            candidates_by_month[month],
            identity_label=f"Tushare money supply month {month}",
        )
        if warning:
            warnings.append(warning)
        if candidate is not None:
            selected.append(candidate)

    resolved = sorted(
        selected,
        key=lambda item: str(item["month"]),
        reverse=True,
    )
    total_count = len(resolved)
    ordered = resolved[:limit]
    rows = [dict(item["row"]) for item in ordered]
    source_versions = [
        str(item["source_version"])
        for item in ordered
        if item.get("source_version")
    ]
    vendor_versions = [
        str(item["vendor_version"])
        for item in ordered
        if item.get("vendor_version")
    ]
    latest = ordered[0]["month"] if ordered else None
    return rows, source_versions, vendor_versions, latest, warnings, total_count


def _load_tushare_money_supply_external_macro(
    conn: duckdb.DuckDBPyConnection,
    *,
    limit: int,
) -> tuple[list[dict[str, object]], list[str], list[str], str | None, list[str], int]:
    raw_rows = conn.execute(
        """
        select trade_date, value_numeric, source_version, vendor_version
        from std_external_macro_daily
        where series_id = 'tushare.macro.cn_money.monthly'
        order by trade_date desc
        """
    ).fetchall()
    candidates_by_month: dict[str, list[dict[str, object]]] = {}
    for trade_date, value_numeric, source_version, vendor_version in raw_rows:
        month = _normalize_iso_date(trade_date)
        if not month:
            continue
        row = {
            "month": month,
            "m0": None,
            "m0_yoy": None,
            "m0_mom": None,
            "m1": None,
            "m1_yoy": None,
            "m1_mom": None,
            "m2": None,
            "m2_yoy": _float_or_none(value_numeric),
            "m2_mom": None,
        }
        candidate = {
            "month": month,
            "row": row,
            "source_version": _string_or_none(source_version),
            "vendor_version": _string_or_none(vendor_version),
            "lineage_key": ("", ""),
            "content_key": _stable_tushare_content_key(
                row,
                source_version=source_version,
                vendor_version=vendor_version,
            ),
        }
        candidates_by_month.setdefault(month, []).append(candidate)

    selected: list[dict[str, object]] = []
    warnings: list[str] = []
    for month in sorted(candidates_by_month, reverse=True):
        candidate, warning = _resolve_tushare_candidate(
            candidates_by_month[month],
            identity_label=f"Tushare fallback money supply month {month}",
        )
        if warning:
            warnings.append(warning)
        if candidate is not None:
            selected.append(candidate)

    resolved = sorted(
        selected,
        key=lambda item: str(item["month"]),
        reverse=True,
    )
    total_count = len(resolved)
    ordered = resolved[:limit]
    rows = [dict(item["row"]) for item in ordered]
    source_versions = [
        str(item["source_version"])
        for item in ordered
        if item.get("source_version")
    ]
    vendor_versions = [
        str(item["vendor_version"])
        for item in ordered
        if item.get("vendor_version")
    ]
    latest = ordered[0]["month"] if ordered else None
    return rows, source_versions, vendor_versions, latest, warnings, total_count


def _load_tushare_eco_calendar_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    *,
    limit: int,
) -> tuple[
    list[dict[str, object]],
    list[str],
    list[str],
    str | None,
    list[str],
    list[str],
    int,
]:
    if "std_tushare_eco_cal_event" not in tables:
        warnings = [] if limit <= 0 else ["Tushare economic calendar table is not materialized."]
        return [], [], [], None, [], warnings, 0
    columns = _duckdb_table_columns(conn, "std_tushare_eco_cal_event")
    select_columns = [
        _column_or_null("event_id", columns),
        _column_or_null("event_date", columns),
        _column_or_null("event_time", columns),
        _column_or_null("currency", columns),
        _column_or_null("country", columns),
        _column_or_null("event", columns),
        _column_or_null("value", columns),
        _column_or_null("pre_value", columns),
        _column_or_null("fore_value", columns),
        _column_or_null("source_version", columns),
        _column_or_null("vendor_version", columns),
        _column_or_null("created_at", columns),
        _column_or_null("ingest_batch_id", columns),
    ]
    raw_rows = conn.execute(
        f"""
        select {", ".join(select_columns)}
        from std_tushare_eco_cal_event
        """
    ).fetchall()
    candidates_by_event_id: dict[str, list[dict[str, object]]] = {}
    for raw in raw_rows:
        event_date = _normalize_iso_date(raw[1])
        if not event_date:
            continue
        event_id = _string_or_none(raw[0]) or _stable_tushare_eco_event_id(
            event_date=event_date,
            event_time=raw[2],
            currency=raw[3],
            country=raw[4],
            event=raw[5],
        )
        row = {
            "event_id": event_id,
            "event_date": event_date,
            "event_time": _string_or_none(raw[2]),
            "currency": _string_or_none(raw[3]),
            "country": _string_or_none(raw[4]),
            "event": _string_or_empty(raw[5]),
            "value": _string_or_none(raw[6]),
            "pre_value": _string_or_none(raw[7]),
            "fore_value": _string_or_none(raw[8]),
        }
        candidate = {
            "event_id": event_id,
            "event_date": event_date,
            "event_time": _string_or_none(raw[2]),
            "row": row,
            "source_version": _string_or_none(raw[9]),
            "vendor_version": _string_or_none(raw[10]),
            "lineage_key": (
                _timestamp_sort_key(raw[11]),
                _string_sort_key(raw[12]),
            ),
            "content_key": _stable_tushare_content_key(
                row,
                source_version=raw[9],
                vendor_version=raw[10],
            ),
        }
        candidates_by_event_id.setdefault(event_id, []).append(candidate)

    selected: list[dict[str, object]] = []
    warnings: list[str] = []
    for event_id in sorted(candidates_by_event_id):
        candidate, warning = _resolve_tushare_candidate(
            candidates_by_event_id[event_id],
            identity_label=f"Tushare economic calendar event {event_id}",
        )
        if warning:
            warnings.append(warning)
        if candidate is not None:
            selected.append(candidate)

    resolved = sorted(
        selected,
        key=lambda item: (
            str(item["event_date"]),
            _time_sort_key(item.get("event_time")),
            str(item["event_id"]),
        ),
        reverse=True,
    )
    total_count = len(resolved)
    ordered = resolved[:limit]
    rows = [dict(item["row"]) for item in ordered]
    source_versions = [
        str(item["source_version"])
        for item in ordered
        if item.get("source_version")
    ]
    vendor_versions = [
        str(item["vendor_version"])
        for item in ordered
        if item.get("vendor_version")
    ]
    latest = ordered[0]["event_date"] if ordered else None
    return (
        rows,
        source_versions,
        vendor_versions,
        latest,
        ["std_tushare_eco_cal_event"],
        warnings,
        total_count,
    )


def _load_bond_futures_rankings_payload(
    duckdb_path: str,
    *,
    contract: str,
    trade_date: str | None,
    limit: int,
) -> tuple[dict[str, object], list[str], list[str], str | None, list[str], list[str]]:
    normalized_contract = normalize_cffex_contract(contract)
    requested_trade_date = normalize_trade_date(trade_date) if trade_date else None
    row_limit = max(0, min(int(limit), 100))
    payload: dict[str, object] = {
        "read_target": "duckdb",
        "as_of_date": None,
        "requested_trade_date": requested_trade_date,
        "contract": normalized_contract,
        "rows": [],
        "warnings": [],
    }
    source_versions: list[str] = []
    vendor_versions: list[str] = []
    warnings: list[str] = []

    duckdb_file = Path(duckdb_path)
    if row_limit <= 0:
        payload["warnings"] = ["Bond futures ranking row limit is zero."]
        return payload, source_versions, vendor_versions, None, payload["warnings"], []
    if not duckdb_file.exists():
        warnings.append("DuckDB file is not available for CFFEX member rankings.")
        payload["warnings"] = warnings
        return payload, source_versions, vendor_versions, None, warnings, []

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error as exc:
        warnings.append(f"DuckDB is not readable for CFFEX member rankings: {exc}")
        payload["warnings"] = warnings
        return payload, source_versions, vendor_versions, None, warnings, []

    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if CFFEX_MEMBER_RANK_TABLE not in tables:
            warnings.append("CFFEX member-rank table is not materialized.")
            payload["warnings"] = warnings
            return payload, source_versions, vendor_versions, None, warnings, []
        source_relation = CFFEX_MEMBER_RANK_VIEW if CFFEX_MEMBER_RANK_VIEW in tables else CFFEX_MEMBER_RANK_TABLE
        resolved_trade_date = requested_trade_date or _latest_bond_futures_trade_date(
            conn,
            source_relation=source_relation,
            contract=normalized_contract,
        )
        payload["as_of_date"] = resolved_trade_date
        tables_used = [CFFEX_MEMBER_RANK_TABLE]
        if source_relation == CFFEX_MEMBER_RANK_VIEW:
            tables_used.append(CFFEX_MEMBER_RANK_VIEW)
        if not resolved_trade_date:
            warnings.append(f"No CFFEX member-rank trade date is available for {normalized_contract}.")
            payload["warnings"] = warnings
            return payload, source_versions, vendor_versions, None, warnings, tables_used

        raw_rows = conn.execute(
            f"""
            select
              trade_date,
              contract,
              product_code,
              exchange,
              member_name,
              source_vendor,
              source_row_no,
              volume,
              volume_change,
              long_holding,
              long_change,
              short_holding,
              short_change,
              source_version,
              vendor_version,
              rule_version
            from {source_relation}
            where trade_date = ? and contract = ?
            order by source_row_no nulls last, member_name
            limit {row_limit}
            """,
            [resolved_trade_date, normalized_contract],
        ).fetchall()
    except duckdb.Error as exc:
        warnings.append(f"CFFEX member-rank query failed: {exc}")
        payload["warnings"] = warnings
        return payload, source_versions, vendor_versions, None, warnings, []
    finally:
        conn.close()

    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        rows.append(
            {
                "trade_date": _string_or_empty(raw[0]),
                "contract": _string_or_empty(raw[1]),
                "product_code": _string_or_empty(raw[2]),
                "exchange": _string_or_empty(raw[3]),
                "member_name": _string_or_empty(raw[4]),
                "source_vendor": _string_or_empty(raw[5]),
                "source_row_no": int(raw[6]) if raw[6] is not None else None,
                "volume": _float_or_none(raw[7]),
                "volume_change": _float_or_none(raw[8]),
                "long_holding": _float_or_none(raw[9]),
                "long_change": _float_or_none(raw[10]),
                "short_holding": _float_or_none(raw[11]),
                "short_change": _float_or_none(raw[12]),
                "source_version": _string_or_none(raw[13]),
                "vendor_version": _string_or_none(raw[14]),
                "rule_version": _string_or_none(raw[15]) or CFFEX_MEMBER_RANK_RULE_VERSION,
            }
        )
        if raw[13]:
            source_versions.append(str(raw[13]))
        if raw[14]:
            vendor_versions.append(str(raw[14]))
    if not rows:
        warnings.append(
            f"CFFEX member-rank table has no rows for {normalized_contract} on {payload['as_of_date']}."
        )
    payload["rows"] = rows
    payload["warnings"] = warnings
    return payload, source_versions, vendor_versions, payload["as_of_date"], warnings, tables_used


def _latest_bond_futures_trade_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    source_relation: str,
    contract: str,
) -> str | None:
    value = conn.execute(
        f"select max(trade_date) from {source_relation} where contract = ?",
        [contract],
    ).fetchone()[0]
    return _string_or_none(value)


def _coverage_section(
    *,
    key: str,
    label: str,
    status: str,
    basis: str,
    formal_use_allowed: bool,
    meta: dict[str, object],
    source_pending: bool,
    proxy_only: bool,
    message: str,
    row_count: int | None = None,
    series_count: int | None = None,
    group_count: int | None = None,
    latest_trade_date: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "basis": basis,
        "formal_use_allowed": formal_use_allowed,
        "quality_flag": _coverage_quality_flag(meta),
        "fallback_mode": _coverage_fallback_mode(meta),
        "vendor_status": _coverage_vendor_status(meta),
        "row_count": row_count,
        "series_count": series_count,
        "group_count": group_count,
        "latest_trade_date": latest_trade_date,
        "as_of_date": as_of_date,
        "source_pending": source_pending,
        "proxy_only": proxy_only,
        "message": message,
    }


def _source_pending_coverage_section(key: str, label: str) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": "source_pending",
        "basis": "analytical",
        "formal_use_allowed": False,
        "quality_flag": "warning",
        "fallback_mode": "none",
        "vendor_status": "vendor_unavailable",
        "row_count": None,
        "series_count": None,
        "group_count": None,
        "latest_trade_date": None,
        "as_of_date": None,
        "source_pending": True,
        "proxy_only": False,
        "message": f"{label} contract is still source-pending.",
    }


def _coverage_quality_flag(meta: dict[str, object]) -> str:
    value = str(meta.get("quality_flag") or "warning")
    return value if value in {"ok", "warning", "error", "stale"} else "warning"


def _coverage_fallback_mode(meta: dict[str, object]) -> str:
    value = str(meta.get("fallback_mode") or "none")
    return value if value in {"none", "latest_snapshot"} else "none"


def _coverage_vendor_status(meta: dict[str, object]) -> str:
    value = str(meta.get("vendor_status") or "ok")
    return value if value in {"ok", "vendor_stale", "vendor_unavailable"} else "ok"


def _fx_formal_coverage_status(result: dict[str, object]) -> str:
    candidate_count = int(result.get("candidate_count") or 0)
    materialized_count = int(result.get("materialized_count") or 0)
    if candidate_count > 0 and materialized_count == candidate_count:
        return "ready"
    if materialized_count > 0:
        return "warning"
    return "empty"


def _latest_choice_series_date(rows: object) -> str | None:
    if not isinstance(rows, list):
        return None
    return _max_normalized_iso_date(
        [
            row.get("trade_date")
            for row in rows
            if isinstance(row, dict) and str(row.get("trade_date") or "").strip()
        ]
    )


def _latest_fx_group_date(groups: object) -> str | None:
    if not isinstance(groups, list):
        return None
    return _max_normalized_iso_date(
        [
            point.get("trade_date")
            for group in groups
            if isinstance(group, dict)
            for point in group.get("series", [])
            if isinstance(point, dict) and str(point.get("trade_date") or "").strip()
        ]
    )


def _result_meta_date(meta: dict[str, object]) -> str | None:
    return _max_normalized_iso_date(
        [
            _string_or_none(meta.get(key))
            for key in ("as_of_date", "resolved_report_date", "fallback_date")
        ]
    )


def _latest_coverage_date(sections: list[dict[str, object]]) -> str | None:
    dates = []
    for section in sections:
        for key in ("latest_trade_date", "as_of_date"):
            value = _string_or_none(section.get(key))
            if value:
                dates.append(value)
    return _max_normalized_iso_date(dates)


def _max_normalized_iso_date(values: list[object]) -> str | None:
    normalized = [
        iso_date
        for iso_date in (_normalize_iso_date(value) for value in values)
        if iso_date is not None
    ]
    return max(normalized) if normalized else None


def _normalize_iso_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None

    candidates = [text, text.replace("/", "-")]
    if len(text) >= 10:
        candidates.append(text[:10].replace("/", "-"))
    for candidate in candidates:
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass

    digits_only = "".join(character for character in text if character.isdigit())
    if len(digits_only) >= 8:
        try:
            return datetime.strptime(digits_only[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            return None
    return None


def _stable_tushare_eco_event_id(
    *,
    event_date: str,
    event_time: object,
    currency: object,
    country: object,
    event: object,
) -> str:
    natural_key = {
        "event_date": event_date,
        "event_time": _time_sort_key(event_time),
        "currency": _normalized_identity_text(currency),
        "country": _normalized_identity_text(country),
        "event": _normalized_identity_text(event),
    }
    encoded = json.dumps(
        natural_key,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"natural-{hashlib.sha256(encoded).hexdigest()[:20]}"


def _normalized_identity_text(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _stable_tushare_content_key(
    row: dict[str, object],
    *,
    source_version: object,
    vendor_version: object,
) -> str:
    return json.dumps(
        {
            "row": row,
            "source_version": _string_or_none(source_version),
            "vendor_version": _string_or_none(vendor_version),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _resolve_tushare_candidate(
    candidates: list[dict[str, object]],
    *,
    identity_label: str,
) -> tuple[dict[str, object] | None, str | None]:
    if len(candidates) == 1:
        return candidates[0], None

    lineage_keys = [
        tuple(candidate.get("lineage_key") or ("", ""))
        for candidate in candidates
    ]
    latest_lineage_key = max(lineage_keys)
    latest_candidates = [
        candidate
        for candidate, lineage_key in zip(candidates, lineage_keys, strict=True)
        if lineage_key == latest_lineage_key
    ]
    if any(latest_lineage_key) and len(latest_candidates) == 1:
        return latest_candidates[0], None

    distinct_content = {
        str(candidate.get("content_key") or "")
        for candidate in latest_candidates
    }
    if len(distinct_content) == 1:
        return min(
            latest_candidates,
            key=lambda candidate: str(candidate.get("content_key") or ""),
        ), None

    if not any(any(lineage_key) for lineage_key in lineage_keys):
        lineage_message = "without created_at/ingest_batch_id"
    else:
        lineage_message = "with indistinguishable created_at/ingest_batch_id lineage"
    return (
        None,
        f"{identity_label} has conflicting duplicate rows {lineage_message}; "
        "omitted because the latest row cannot be determined.",
    )


def _timestamp_sort_key(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo is not None else value
        return normalized.isoformat()
    text = _string_or_none(value)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    normalized = parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed
    return normalized.isoformat()


def _time_sort_key(value: object) -> str:
    text = _string_or_none(value)
    if not text:
        return ""
    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, time_format).time().isoformat()
        except ValueError:
            continue
    return text


def _string_sort_key(value: object) -> str:
    return _string_or_none(value) or ""


def _coverage_actions(sections: list[dict[str, object]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for section in sections:
        if section["source_pending"]:
            actions.append(
                {
                    "key": str(section["key"]),
                    "label": f"{section['label']} remains source-pending.",
                    "severity": "warning",
                    "target_anchor": "market-data-source-pending-deck",
                }
            )
        elif section["proxy_only"]:
            actions.append(
                {
                    "key": str(section["key"]),
                    "label": f"{section['label']} is proxy-only.",
                    "severity": "warning",
                    "target_anchor": "market-data-liquidity-deck",
                }
            )
    return actions


def _coverage_evidence_count(section: dict[str, object]) -> int:
    for key in ("row_count", "series_count", "group_count"):
        value = section.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 0


def _meta_text(envelope: dict[str, object], key: str) -> str:
    meta = envelope.get("result_meta", {})
    if not isinstance(meta, dict):
        return ""
    return str(meta.get(key) or "")


def _duckdb_table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _column_or_null(column_name: str, columns: set[str]) -> str:
    if column_name in columns:
        return column_name
    return f"NULL as {column_name}"


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_empty(value: object) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _string_or_none(value: object) -> str | None:
    text = _string_or_empty(value).strip()
    return text or None


def load_fx_formal_status_payload(duckdb_path: str) -> FxFormalStatusPayload:
    settings = get_settings()
    try:
        candidates = discover_formal_fx_candidates(
            catalog_path=Path(settings.choice_macro_catalog_file)
        )
    except FileNotFoundError:
        return FxFormalStatusPayload(
            candidate_count=0,
            materialized_count=0,
            latest_trade_date=None,
            carry_forward_count=0,
            rows=[],
        )
    rows_by_pair = _load_latest_fx_mid_rows(
        duckdb_path=duckdb_path,
        base_currencies=[candidate.base_currency for candidate in candidates],
    )

    rows: list[FxFormalStatusRow] = []
    latest_trade_dates: list[str] = []
    carry_forward_count = 0
    materialized_count = 0
    for candidate in candidates:
        current = rows_by_pair.get((candidate.base_currency, candidate.quote_currency))
        status = "ok" if current is not None else "missing"
        if current is not None:
            materialized_count += 1
            if current["trade_date"]:
                latest_trade_dates.append(current["trade_date"])
            if current["is_carry_forward"]:
                carry_forward_count += 1
        rows.append(
            FxFormalStatusRow(
                base_currency=candidate.base_currency,
                quote_currency=candidate.quote_currency,
                pair_label=candidate.pair_label,
                series_id=candidate.series_id,
                series_name=candidate.series_name,
                vendor_series_code=candidate.vendor_series_code,
                trade_date=current["trade_date"] if current is not None else None,
                observed_trade_date=current["observed_trade_date"] if current is not None else None,
                mid_rate=current["mid_rate"] if current is not None else None,
                source_name=current["source_name"] if current is not None else None,
                vendor_name=current["vendor_name"] if current is not None else None,
                vendor_version=current["vendor_version"] if current is not None else None,
                source_version=current["source_version"] if current is not None else None,
                is_business_day=current["is_business_day"] if current is not None else None,
                is_carry_forward=current["is_carry_forward"] if current is not None else None,
                status=status,
            )
        )

    latest_trade_date = max(latest_trade_dates) if latest_trade_dates else None
    return FxFormalStatusPayload(
        candidate_count=len(candidates),
        materialized_count=materialized_count,
        latest_trade_date=latest_trade_date,
        carry_forward_count=carry_forward_count,
        rows=rows,
    )


def fx_formal_status_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_fx_formal_status_payload(duckdb_path)
    source_version = _aggregate_lineage_value(
        [row.source_version or "" for row in payload.rows if row.status == "ok"],
        empty_value="sv_fx_formal_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [row.vendor_version or "" for row in payload.rows if row.status == "ok"],
        empty_value="vv_none",
    )
    quality_flag = (
        "ok"
        if payload.candidate_count > 0 and payload.candidate_count == payload.materialized_count
        else "warning"
    )
    return build_result_envelope(
        basis="formal",
        trace_id="tr_fx_formal_status",
        result_kind="fx.formal.status",
        cache_version="cv_fx_formal_mid_v1",
        source_version=source_version,
        rule_version="rv_fx_formal_mid_v1",
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status="ok" if payload.materialized_count and payload.candidate_count else "vendor_unavailable",
        fallback_mode="latest_snapshot" if payload.carry_forward_count else "none",
        result_payload=payload.model_dump(mode="json"),
    )


def load_fx_analytical_payload(duckdb_path: str) -> FxAnalyticalPayload:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return FxAnalyticalPayload(groups=[])

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return FxAnalyticalPayload(groups=[])

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fact_choice_macro_daily" not in tables or "phase1_macro_vendor_catalog" not in tables:
            return FxAnalyticalPayload(groups=[])
        recent_rows = _load_choice_macro_recent_rows(conn, tables)
        catalog_by_series = _load_choice_macro_catalog_map(conn, tables)
        name_by_series = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                """
                select distinct series_id, series_name
                from phase1_macro_vendor_catalog
                """
            ).fetchall()
        }
    except duckdb.Error:
        return FxAnalyticalPayload(groups=[])
    finally:
        conn.close()

    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for (
        series_id,
        series_name,
        trade_date,
        value_numeric,
        frequency,
        unit,
        source_version,
        vendor_version,
        quality_flag,
        _rn,
    ) in recent_rows:
        logical_name = name_by_series.get(str(series_id), str(series_name))
        group_key = classify_fx_series_group(logical_name)
        if group_key is None:
            continue
        grouped_rows.setdefault(str(series_id), []).append(
            {
                "group_key": group_key,
                "series_id": str(series_id),
                "series_name": logical_name,
                "trade_date": str(trade_date),
                "value_numeric": float(value_numeric),
                "frequency": str(frequency),
                "unit": str(unit),
                "source_version": str(source_version),
                "vendor_version": str(vendor_version),
                "quality_flag": str(quality_flag),
            }
        )

    groups: dict[str, list[FxAnalyticalSeriesPoint]] = {}
    for series_id, rows in grouped_rows.items():
        latest = _resolve_fx_analytical_latest_row(rows)
        recent_points = [
            ChoiceMacroRecentPoint(
                trade_date=str(row["trade_date"]),
                value_numeric=float(row["value_numeric"]),
                source_version=str(row["source_version"]),
                vendor_version=str(row["vendor_version"]),
                quality_flag=_normalize_quality_flag(str(row["quality_flag"])),
            )
            for row in rows
        ]
        latest_change = None
        if len(rows) > 1:
            latest_change = float(rows[0]["value_numeric"]) - float(rows[1]["value_numeric"])
        catalog = catalog_by_series.get(
            series_id,
            {
                "refresh_tier": None,
                "fetch_mode": None,
                "fetch_granularity": None,
                "policy_note": None,
            },
        )
        point = FxAnalyticalSeriesPoint(
            group_key=latest["group_key"],
            series_id=series_id,
            series_name=str(latest["series_name"]),
            trade_date=str(latest["trade_date"]),
            value_numeric=float(latest["value_numeric"]),
            frequency=str(latest["frequency"]),
            unit=str(latest["unit"]),
            source_version=str(latest["source_version"]),
            vendor_version=str(latest["vendor_version"]),
            refresh_tier=_as_optional_string(catalog.get("refresh_tier")),
            fetch_mode=_as_optional_string(catalog.get("fetch_mode")),
            fetch_granularity=_as_optional_string(catalog.get("fetch_granularity")),
            policy_note=_as_optional_string(catalog.get("policy_note")),
            quality_flag=_normalize_quality_flag(str(latest["quality_flag"])),
            latest_change=latest_change,
            recent_points=recent_points,
        )
        groups.setdefault(latest["group_key"], []).append(point)

    ordered_groups: list[FxAnalyticalGroup] = []
    for group_key, title, description in (
        ("middle_rate", "Analytical FX: middle-rates", "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam."),
        ("fx_index", "Analytical FX: indices", "RMB index / estimate index series stay analytical-only and never flow into formal FX."),
        ("fx_swap_curve", "Analytical FX: swap curves", "FX swap / C-Swap series stay analytical-only and never write into formal FX."),
    ):
        points = sorted(groups.get(group_key, []), key=lambda item: item.series_id)
        if not points:
            continue
        ordered_groups.append(
            FxAnalyticalGroup(
                group_key=group_key,
                title=title,
                description=description,
                series=points,
            )
        )
    return FxAnalyticalPayload(groups=ordered_groups)


def _resolve_fx_analytical_latest_row(rows: list[dict[str, object]]) -> dict[str, object]:
    latest = rows[0]
    if not _is_usd_cny_middle_rate(str(latest["series_name"])):
        return latest
    target_date = date.fromisoformat(str(latest["trade_date"]))
    rate, observed_date, warnings = get_usd_cny_rate(
        [
            (date.fromisoformat(str(row["trade_date"])), Decimal(str(row["value_numeric"])))
            for row in rows
        ],
        target_date,
        allow_stale_fallback=True,
    )
    quality_flag = "warning" if warnings else str(latest["quality_flag"])
    return {
        **latest,
        "trade_date": observed_date.isoformat() if observed_date is not None else str(latest["trade_date"]),
        "value_numeric": float(rate),
        "quality_flag": quality_flag,
    }


def _is_usd_cny_middle_rate(series_name: str) -> bool:
    return "中间价" in series_name and "美元" in series_name and "人民币" in series_name


def fx_analytical_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_fx_analytical_payload(duckdb_path)
    points = [
        point
        for group in payload.groups
        for point in group.series
    ]
    source_version = _aggregate_lineage_value(
        [point.source_version for point in points],
        empty_value="sv_fx_analytical_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [point.vendor_version for point in points],
        empty_value="vv_none",
    )
    quality_flag = _aggregate_quality_flags([point.quality_flag for point in points])
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_fx_analytical",
        result_kind="fx.analytical.groups",
        cache_version="cv_fx_analytical_v1",
        source_version=source_version,
        rule_version="rv_fx_analytical_v1",
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=_vendor_status_for_presence(points),
        fallback_mode="latest_snapshot" if any(point.refresh_tier == "fallback" for point in points) else "none",
        result_payload=payload.model_dump(mode="json"),
    )


def choice_macro_refresh_status(governance_path: str | Path, *, run_id: str = "") -> dict[str, object]:
    records = [
        record
        for record in GovernanceRepository(base_dir=governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name")) == CHOICE_MACRO_REFRESH_JOB_NAME
        and str(record.get("cache_key")) == CHOICE_MACRO_REFRESH_CACHE_KEY
    ]
    if run_id:
        records = [record for record in records if str(record.get("run_id")) == run_id]
        if not records:
            raise ValueError(f"Unknown choice macro refresh run_id={run_id}")
    if not records:
        return {
            "status": "idle",
            "job_name": CHOICE_MACRO_REFRESH_JOB_NAME,
            "cache_key": CHOICE_MACRO_REFRESH_CACHE_KEY,
            "trigger_mode": "idle",
        }
    latest = records[-1]
    status = str(latest.get("status", "unknown"))
    return {
        **latest,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
    }


def _load_latest_fx_mid_rows(
    *,
    duckdb_path: str,
    base_currencies: list[str],
) -> dict[tuple[str, str], dict[str, object]]:
    if not base_currencies:
        return {}
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return {}
    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return {}
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fx_daily_mid" not in tables:
            return {}
        placeholders = ", ".join(["?"] * len(base_currencies))
        rows = conn.execute(
            f"""
            with ranked as (
              select
                base_currency,
                quote_currency,
                cast(trade_date as varchar) as trade_date,
                cast(observed_trade_date as varchar) as observed_trade_date,
                cast(mid_rate as double) as mid_rate,
                source_name,
                coalesce(vendor_name, '') as vendor_name,
                coalesce(vendor_version, '') as vendor_version,
                source_version,
                is_business_day,
                is_carry_forward,
                row_number() over (
                  partition by upper(base_currency), upper(quote_currency)
                  order by trade_date desc
                ) as rn
              from fx_daily_mid
              where upper(base_currency) in ({placeholders})
                and upper(quote_currency) = 'CNY'
            )
            select
              base_currency,
              quote_currency,
              trade_date,
              observed_trade_date,
              mid_rate,
              source_name,
              vendor_name,
              vendor_version,
              source_version,
              is_business_day,
              is_carry_forward
            from ranked
            where rn = 1
            """,
            [item.upper() for item in base_currencies],
        ).fetchall()
    except duckdb.Error:
        return {}
    finally:
        conn.close()

    result: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row[0]).upper(), str(row[1]).upper())
        result[key] = {
            "base_currency": str(row[0]).upper(),
            "quote_currency": str(row[1]).upper(),
            "trade_date": str(row[2]) if row[2] is not None else None,
            "observed_trade_date": str(row[3]) if row[3] is not None else None,
            "mid_rate": float(row[4]) if row[4] is not None else None,
            "source_name": str(row[5]) if row[5] is not None else None,
            "vendor_name": str(row[6]) if row[6] is not None else None,
            "vendor_version": str(row[7]) if row[7] is not None else None,
            "source_version": str(row[8]) if row[8] is not None else None,
            "is_business_day": bool(row[9]) if row[9] is not None else None,
            "is_carry_forward": bool(row[10]) if row[10] is not None else None,
        }
    return result


_CHOICE_MACRO_RECENT_POINT_LIMIT = 20


def _load_choice_macro_recent_rows(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> list[tuple[object, ...]]:
    if "choice_market_snapshot" in tables:
        snapshot_count = conn.execute(
            "select count(*) from choice_market_snapshot"
        ).fetchone()
        if snapshot_count and int(snapshot_count[0]) > 0:
            return conn.execute(
                f"""
                with active_series as (
                  select distinct series_id
                  from choice_market_snapshot
                ),
                ranked as (
                  select
                    fact.series_id,
                    fact.series_name,
                    fact.trade_date,
                    fact.value_numeric,
                    fact.frequency,
                    fact.unit,
                    fact.source_version,
                    fact.vendor_version,
                    fact.quality_flag,
                    row_number() over(partition by fact.series_id order by fact.trade_date desc) as rn
                  from fact_choice_macro_daily as fact
                  inner join active_series on active_series.series_id = fact.series_id
                )
                select
                  series_id,
                  series_name,
                  trade_date,
                  value_numeric,
                  frequency,
                  unit,
                  source_version,
                  vendor_version,
                  quality_flag,
                  rn
                from ranked
                where rn <= {_CHOICE_MACRO_RECENT_POINT_LIMIT}
                order by series_id, rn
                """
            ).fetchall()

    return conn.execute(
        f"""
        with ranked as (
          select
            series_id,
            series_name,
            trade_date,
            value_numeric,
            frequency,
            unit,
            source_version,
            vendor_version,
            quality_flag,
            row_number() over(partition by series_id order by trade_date desc) as rn
          from fact_choice_macro_daily
        )
        select
          series_id,
          series_name,
          trade_date,
          value_numeric,
          frequency,
          unit,
          source_version,
          vendor_version,
          quality_flag,
          rn
        from ranked
        where rn <= {_CHOICE_MACRO_RECENT_POINT_LIMIT}
        order by series_id, rn
        """
    ).fetchall()


def _load_choice_macro_catalog_map(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> dict[str, dict[str, object]]:
    if "phase1_macro_vendor_catalog" not in tables:
        return {}

    category_by_series = _load_market_data_category_map(conn, tables)
    available_columns = {
        str(row[1])
        for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
    }
    select_columns = [
        "series_id",
        _catalog_column_expr("vendor_name", available_columns, "NULL"),
        _catalog_column_expr("refresh_tier", available_columns, "NULL"),
        _catalog_column_expr("fetch_mode", available_columns, "NULL"),
        _catalog_column_expr("fetch_granularity", available_columns, "NULL"),
        _catalog_column_expr("policy_note", available_columns, "NULL"),
        "frequency",
        "unit",
    ]
    rows = conn.execute(
        f"""
        select
          {", ".join(select_columns)}
        from phase1_macro_vendor_catalog
        """
    ).fetchall()

    catalog_by_series: dict[str, dict[str, object]] = {}
    for (
        series_id,
        vendor_name,
        refresh_tier,
        fetch_mode,
        fetch_granularity,
        policy_note,
        frequency,
        unit,
    ) in rows:
        category = category_by_series.get(str(series_id), {})
        catalog_by_series[str(series_id)] = {
            "vendor_name": _as_optional_string(vendor_name),
            "refresh_tier": _sanitize_choice_macro_refresh_tier(
                category.get("refresh_tier") or refresh_tier
            ),
            "fetch_mode": _sanitize_choice_macro_fetch_mode(category.get("fetch_mode") or fetch_mode),
            "fetch_granularity": _sanitize_choice_macro_fetch_granularity(
                category.get("fetch_granularity") or fetch_granularity
            ),
            "policy_note": _as_optional_string(category.get("policy_note") or policy_note),
            "frequency": str(frequency or ""),
            "unit": str(unit or ""),
        }
    return catalog_by_series


def _load_market_data_category_map(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> dict[str, dict[str, object]]:
    if "market_data_series_category" not in tables:
        return {}

    available_columns = {
        str(row[1])
        for row in conn.execute("pragma table_info('market_data_series_category')").fetchall()
    }
    if "series_id" not in available_columns:
        return {}

    refresh_expr = "category_key" if "category_key" in available_columns else "NULL"
    rows = conn.execute(
        f"""
        select
          series_id,
          {refresh_expr},
          {_catalog_column_expr("fetch_mode", available_columns, "NULL")},
          {_catalog_column_expr("fetch_granularity", available_columns, "NULL")},
          {_catalog_column_expr("policy_note", available_columns, "NULL")}
        from market_data_series_category
        """
    ).fetchall()

    category_by_series: dict[str, dict[str, object]] = {}
    for series_id, refresh_tier, fetch_mode, fetch_granularity, policy_note in rows:
        category_by_series[str(series_id)] = {
            "refresh_tier": _sanitize_choice_macro_refresh_tier(refresh_tier),
            "fetch_mode": _sanitize_choice_macro_fetch_mode(fetch_mode),
            "fetch_granularity": _sanitize_choice_macro_fetch_granularity(fetch_granularity),
            "policy_note": _as_optional_string(policy_note),
        }
    return category_by_series


def _catalog_column_expr(column: str, available_columns: set[str], fallback_sql: str) -> str:
    if column in available_columns:
        return column
    return f"{fallback_sql} as {column}"


def _aggregate_lineage_value(values: list[str], empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)


def _quality_flag_for_presence(series: list[object]) -> str:
    return "ok" if series else "warning"


def _vendor_status_for_presence(series: list[object]) -> str:
    return "ok" if series else "vendor_unavailable"


def _vendor_status_for_macro_latest(payload: ChoiceMacroLatestPayload, quality_flag: str) -> str:
    if not payload.series:
        return "vendor_unavailable"
    if quality_flag == "stale":
        return "vendor_stale"
    return "ok"


def _fallback_mode_for_macro_latest(payload: ChoiceMacroLatestPayload, quality_flag: str) -> str:
    if payload.series and quality_flag == "stale":
        return "latest_snapshot"
    return "none"


def _aggregate_quality_flags(values: list[str]) -> str:
    normalized = {_normalize_quality_flag(value) for value in values if value}
    if not normalized:
        return "warning"
    for flag in ("error", "stale", "warning"):
        if flag in normalized:
            return flag
    return "ok"


def _normalize_quality_flag(value: str) -> str:
    if value in {"ok", "warning", "error", "stale"}:
        return value
    return "warning"


def _as_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _parse_string_list_json(value: object) -> list[str]:
    text = _as_optional_string(value)
    if text is None:
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [
        normalized
        for item in parsed
        if isinstance(item, str) and (normalized := item.strip())
    ]


def _sanitize_choice_macro_refresh_tier(value: object) -> str | None:
    return _sanitize_choice_macro_literal(value, CHOICE_MACRO_REFRESH_TIERS)


def _sanitize_choice_macro_fetch_mode(value: object) -> str | None:
    return _sanitize_choice_macro_literal(value, CHOICE_MACRO_FETCH_MODES)


def _sanitize_choice_macro_fetch_granularity(value: object) -> str | None:
    return _sanitize_choice_macro_literal(value, CHOICE_MACRO_FETCH_GRANULARITIES)


def _sanitize_choice_macro_literal(value: object, allowed_values: set[str]) -> str | None:
    text = _as_optional_string(value)
    if text is None:
        return None
    return text if text in allowed_values else None
