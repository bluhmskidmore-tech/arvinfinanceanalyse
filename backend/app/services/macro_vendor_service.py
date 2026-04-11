from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.schemas.macro_vendor import (
    ChoiceMacroLatestPayload,
    ChoiceMacroLatestPoint,
    ChoiceMacroRecentPoint,
    MacroVendorPayload,
    MacroVendorSeries,
)
from backend.app.schemas.result_meta import ResultMeta

RULE_VERSION = "rv_phase1_macro_vendor_v1"
CACHE_VERSION = "cv_phase1_macro_vendor_v1"
LIVE_RULE_VERSION = "rv_choice_macro_thin_slice_v1"
LIVE_CACHE_VERSION = "cv_choice_macro_thin_slice_v1"


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

        rows = conn.execute(
            """
            select series_id, series_name, vendor_name, vendor_version, frequency, unit
            from phase1_macro_vendor_catalog
            order by vendor_name, series_id
            """
        ).fetchall()
    except duckdb.Error:
        return MacroVendorPayload(series=[])
    finally:
        conn.close()

    return MacroVendorPayload(
        series=[
            MacroVendorSeries(
                series_id=str(series_id),
                series_name=str(series_name),
                vendor_name=str(vendor_name),
                vendor_version=str(vendor_version),
                frequency=str(frequency),
                unit=str(unit),
            )
            for series_id, series_name, vendor_name, vendor_version, frequency, unit in rows
        ]
    )


def macro_vendor_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_macro_vendor_payload(duckdb_path)
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in payload.series],
        empty_value="vv_none",
    )
    meta = ResultMeta(
        trace_id="tr_preview_macro_foundation",
        basis="analytical",
        result_kind="preview.macro-foundation",
        formal_use_allowed=False,
        source_version="sv_macro_vendor_empty",
        vendor_version=vendor_version,
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag=_quality_flag_for_presence(payload.series),
        scenario_flag=False,
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def load_choice_macro_latest_payload(duckdb_path: str) -> ChoiceMacroLatestPayload:
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
                "refresh_tier": None,
                "fetch_mode": None,
                "fetch_granularity": None,
                "policy_note": None,
            },
        )
        if catalog.get("refresh_tier") == "isolated":
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
                refresh_tier=_as_optional_string(catalog.get("refresh_tier")),
                fetch_mode=_as_optional_string(catalog.get("fetch_mode")),
                fetch_granularity=_as_optional_string(catalog.get("fetch_granularity")),
                policy_note=_as_optional_string(catalog.get("policy_note")),
                quality_flag=_normalize_quality_flag(str(latest["quality_flag"])),
                latest_change=latest_change,
                recent_points=recent_points,
            )
        )

    return ChoiceMacroLatestPayload(series=series)


def choice_macro_latest_envelope(duckdb_path: str) -> dict[str, object]:
    payload = load_choice_macro_latest_payload(duckdb_path)
    source_version = _aggregate_lineage_value(
        [item.source_version for item in payload.series],
        empty_value="sv_choice_macro_empty",
    )
    vendor_version = _aggregate_lineage_value(
        [item.vendor_version for item in payload.series],
        empty_value="vv_none",
    )
    meta = ResultMeta(
        trace_id="tr_choice_macro_latest",
        basis="analytical",
        result_kind="macro.choice.latest",
        formal_use_allowed=False,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=LIVE_RULE_VERSION,
        cache_version=LIVE_CACHE_VERSION,
        quality_flag=_aggregate_quality_flags([item.quality_flag for item in payload.series]),
        scenario_flag=False,
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


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
                """
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
                where rn <= 3
                order by series_id, rn
                """
            ).fetchall()

    return conn.execute(
        """
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
        where rn <= 3
        order by series_id, rn
        """
    ).fetchall()


def _load_choice_macro_catalog_map(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
) -> dict[str, dict[str, object]]:
    if "phase1_macro_vendor_catalog" not in tables:
        return {}

    available_columns = {
        str(row[1])
        for row in conn.execute("pragma table_info('phase1_macro_vendor_catalog')").fetchall()
    }
    select_columns = [
        "series_id",
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
        refresh_tier,
        fetch_mode,
        fetch_granularity,
        policy_note,
        frequency,
        unit,
    ) in rows:
        catalog_by_series[str(series_id)] = {
            "refresh_tier": _as_optional_string(refresh_tier),
            "fetch_mode": _as_optional_string(fetch_mode),
            "fetch_granularity": _as_optional_string(fetch_granularity),
            "policy_note": _as_optional_string(policy_note),
            "frequency": str(frequency or ""),
            "unit": str(unit or ""),
        }
    return catalog_by_series


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
