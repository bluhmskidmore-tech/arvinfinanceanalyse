"""Backfill sparse rows in ``fact_choice_macro_daily`` from Choice / Tushare / Wind / AkShare."""

from __future__ import annotations

import json
import logging
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import duckdb

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_choice_macro_schema_if_missing,
)
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)

logger = logging.getLogger(__name__)

SOURCE_VERSION = "backfill_macro_v1"
RULE_VERSION = "rv_backfill_macro_v1"
MIN_ROW_THRESHOLD = 10
LOCK = LockDefinition(key="lock:duckdb:macro-series-backfill", ttl_seconds=900)


class BackfillSource(str, Enum):
    CHOICE_SNAPSHOT = "choice_snapshot"
    CHOICE_EDB = "choice_edb"
    TUSHARE_MACRO = "tushare_macro"
    WIND = "wind"
    AKSHARE = "akshare"


@dataclass(frozen=True)
class IncompleteSeries:
    series_id: str
    series_name: str
    row_count: int
    frequency: str
    unit: str
    vendor_series_code: str


@dataclass(frozen=True)
class BackfillRow:
    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str


@dataclass(frozen=True)
class SeriesBackfillPlan:
    series_id: str
    series_name: str
    existing_rows: int
    start_date: str
    end_date: str
    frequency: str
    unit: str
    sources: tuple[BackfillSource, ...]
    snapshot_rows_in_range: int
    notes: str


def backfill_macro_series(
    *,
    duckdb_path: str,
    series_names: list[str] | None = None,
    start_date: str = "2024-01-01",
    end_date: str | None = None,
    dry_run: bool = False,
    sources_filter: list[str] | None = None,
) -> dict:
    """Backfill macro series with fewer than ``MIN_ROW_THRESHOLD`` rows in DuckDB."""
    resolved_end = end_date or date.today().isoformat()
    _validate_iso_date(start_date, field_name="start_date")
    _validate_iso_date(resolved_end, field_name="end_date")
    if resolved_end < start_date:
        raise ValueError("end_date must be on or after start_date.")

    db_path = Path(duckdb_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {db_path}")

    incomplete = _load_incomplete_series(db_path, series_names=series_names)
    plans = [_build_plan(conn_path=db_path, item=item, start_date=start_date, end_date=resolved_end) for item in incomplete]
    allowed_sources: set[str] | None = None
    if sources_filter:
        allowed_sources = {source.strip() for source in sources_filter if source.strip()}
        filtered = [
            (item, plan)
            for item, plan in zip(incomplete, plans, strict=True)
            if plan.sources and any(source.value in allowed_sources for source in plan.sources)
        ]
        if filtered:
            incomplete, plans = map(list, zip(*filtered, strict=True))
        else:
            incomplete = []
            plans = []

    if dry_run:
        allocation: dict[str, int] = {}
        for plan in plans:
            display_sources = _filter_plan_sources(plan.sources, allowed_sources)
            primary = display_sources[0].value if display_sources else "unclassified"
            allocation[primary] = allocation.get(primary, 0) + 1
        return {
            "dry_run": True,
            "duckdb_path": str(db_path),
            "start_date": start_date,
            "end_date": resolved_end,
            "incomplete_count": len(plans),
            "source_allocation": allocation,
            "series_plans": [
                {
                    "series_name": plan.series_name,
                    "series_id": plan.series_id,
                    "existing_rows": plan.existing_rows,
                    "start_date": plan.start_date,
                    "end_date": plan.end_date,
                    "frequency": plan.frequency,
                    "sources": [source.value for source in _filter_plan_sources(plan.sources, allowed_sources)],
                    "snapshot_rows_in_range": plan.snapshot_rows_in_range,
                    "notes": plan.notes,
                }
                for plan in plans
            ],
        }

    results: dict[str, int] = {}
    errors: dict[str, str] = {}
    run_id = f"backfill_macro_v1:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
    vendor_version = f"vv_backfill_macro_{resolved_end.replace('-', '')}"

    with acquire_lock(LOCK, base_dir=db_path.parent):
        conn = duckdb.connect(str(db_path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            ensure_choice_macro_schema_if_missing(conn)
            for item, plan in zip(incomplete, plans, strict=True):
                try:
                    rows = _fetch_rows_for_plan(
                        plan,
                        duckdb_path=db_path,
                        vendor_series_code=item.vendor_series_code,
                        start_date=start_date,
                        end_date=resolved_end,
                        sources_filter=sources_filter,
                    )
                    added = _insert_rows(
                        conn,
                        rows=rows,
                        source_version=SOURCE_VERSION,
                        vendor_version=vendor_version,
                        run_id=run_id,
                    )
                    results[item.series_name] = added
                except Exception as exc:
                    logger.exception(
                        "macro backfill failed series=%s error=%s",
                        item.series_name,
                        exc,
                    )
                    errors[item.series_name] = str(exc)
                    results[item.series_name] = 0
            conn.close()
        except Exception:
            conn.close()
            raise

    return {
        "dry_run": False,
        "duckdb_path": str(db_path),
        "start_date": start_date,
        "end_date": resolved_end,
        "processed_count": len(incomplete),
        "total_added": sum(results.values()),
        "results": results,
        "errors": errors,
    }


def _load_incomplete_series(db_path: Path, *, series_names: list[str] | None) -> list[IncompleteSeries]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        has_catalog = _relation_exists(conn, "phase1_macro_vendor_catalog")
        if has_catalog:
            catalog_columns = _table_columns(conn, "phase1_macro_vendor_catalog")
            catalog_name_expr = "cat.series_name" if "series_name" in catalog_columns else "f.series_name"
            catalog_frequency_expr = "cat.frequency" if "frequency" in catalog_columns else "'unknown'"
            catalog_unit_expr = "cat.unit" if "unit" in catalog_columns else "'unknown'"
            catalog_vendor_code_expr = (
                "cat.vendor_series_code" if "vendor_series_code" in catalog_columns else "cat.series_id"
            )
            name_filter = ""
            params: list[object] = [MIN_ROW_THRESHOLD]
            if series_names:
                placeholders = ", ".join(["?"] * len(series_names))
                name_filter = f"and series_name in ({placeholders})"
                params.extend(series_names)
            query = f"""
                with fact_counts as (
                  select series_id, max(series_name) as series_name, count(*) as row_count
                  from fact_choice_macro_daily
                  group by series_id
                ),
                catalog_series as (
                  select
                    cat.series_id,
                    coalesce(nullif({catalog_name_expr}, ''), f.series_name, cat.series_id) as series_name,
                    coalesce(f.row_count, 0) as row_count,
                    coalesce({catalog_frequency_expr}, 'unknown') as frequency,
                    coalesce({catalog_unit_expr}, 'unknown') as unit,
                    coalesce({catalog_vendor_code_expr}, cat.series_id) as vendor_series_code
                  from phase1_macro_vendor_catalog cat
                  left join fact_counts f on f.series_id = cat.series_id
                ),
                fact_only_series as (
                  select
                    f.series_id,
                    f.series_name,
                    f.row_count,
                    'unknown' as frequency,
                    'unknown' as unit,
                    f.series_id as vendor_series_code
                  from fact_counts f
                  left join phase1_macro_vendor_catalog cat on cat.series_id = f.series_id
                  where cat.series_id is null
                ),
                all_series as (
                  select * from catalog_series
                  union all
                  select * from fact_only_series
                )
                select series_id, series_name, row_count, frequency, unit, vendor_series_code
                from all_series
                where row_count < ?
                {name_filter}
                order by series_name
            """
        else:
            if series_names:
                placeholders = ", ".join(["?"] * len(series_names))
                name_filter = f"where series_name in ({placeholders})"
                params = [*series_names, MIN_ROW_THRESHOLD]
            else:
                name_filter = ""
                params = [MIN_ROW_THRESHOLD]
            query = f"""
                with counts as (
                  select series_id, series_name, count(*) as row_count
                  from fact_choice_macro_daily
                  {name_filter}
                  group by series_id, series_name
                )
                select
                  series_id,
                  series_name,
                  row_count,
                  'unknown' as frequency,
                  'unknown' as unit,
                  series_id as vendor_series_code
                from counts
                where row_count < ?
                order by series_name
            """
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    return [
        IncompleteSeries(
            series_id=str(row[0]),
            series_name=str(row[1]),
            row_count=int(row[2]),
            frequency=str(row[3]),
            unit=str(row[4]),
            vendor_series_code=str(row[5]),
        )
        for row in rows
    ]


def _build_plan(
    *,
    conn_path: Path,
    item: IncompleteSeries,
    start_date: str,
    end_date: str,
) -> SeriesBackfillPlan:
    snapshot_rows = _count_snapshot_rows(
        conn_path,
        series_id=item.series_id,
        start_date=start_date,
        end_date=end_date,
    )
    sources = _resolve_sources(item.series_name, item.series_id, snapshot_rows=snapshot_rows)
    notes = _plan_notes(item.series_name, sources)
    frequency = _infer_frequency(item.series_name, item.frequency)
    return SeriesBackfillPlan(
        series_id=item.series_id,
        series_name=item.series_name,
        existing_rows=item.row_count,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        unit=item.unit,
        sources=sources,
        snapshot_rows_in_range=snapshot_rows,
        notes=notes,
    )


def _resolve_sources(series_name: str, series_id: str, *, snapshot_rows: int) -> tuple[BackfillSource, ...]:
    name = series_name.upper()

    if _is_commodity_series(series_name):
        return (BackfillSource.AKSHARE, BackfillSource.TUSHARE_MACRO)

    if _is_tushare_macro_series(series_name):
        return (BackfillSource.TUSHARE_MACRO, BackfillSource.CHOICE_EDB)

    if _is_spread_series(series_name):
        return (BackfillSource.WIND, BackfillSource.CHOICE_EDB)

    if _is_daily_rate_series(series_name, series_id):
        sources: list[BackfillSource] = []
        if snapshot_rows > 0:
            sources.append(BackfillSource.CHOICE_SNAPSHOT)
        sources.extend([BackfillSource.CHOICE_EDB, BackfillSource.WIND])
        if "DR007" in name or series_id == "CA.DR007":
            sources.insert(1 if sources and sources[0] == BackfillSource.CHOICE_SNAPSHOT else 0, BackfillSource.AKSHARE)
        if "SHIBOR" in name or series_id.startswith("NCD.SHIBOR."):
            sources.insert(1 if sources and sources[0] == BackfillSource.CHOICE_SNAPSHOT else 0, BackfillSource.TUSHARE_MACRO)
        return tuple(_dedupe_sources(sources))

    if series_id.startswith("EMM") or series_id.startswith("NCD."):
        return (BackfillSource.CHOICE_EDB, BackfillSource.TUSHARE_MACRO)

    return (BackfillSource.CHOICE_EDB,)


def _plan_notes(series_name: str, sources: tuple[BackfillSource, ...]) -> str:
    if BackfillSource.WIND in sources and not _wind_available():
        return "WindPy unavailable; will fall back to next source in chain."
    if BackfillSource.TUSHARE_MACRO in sources and not _tushare_token_configured():
        return "MOSS_TUSHARE_TOKEN missing; Tushare leg may be skipped."
    if BackfillSource.CHOICE_EDB in sources:
        return "Choice EDB historical window backfill."
    if BackfillSource.AKSHARE in sources and _is_commodity_series(series_name):
        return "Public commodity lane via AkShare."
    return "Backfill plan resolved from series name/id."


def _fetch_rows_for_plan(
    plan: SeriesBackfillPlan,
    *,
    duckdb_path: Path,
    vendor_series_code: str,
    start_date: str,
    end_date: str,
    sources_filter: list[str] | None = None,
) -> list[BackfillRow]:
    allowed = {source.strip() for source in sources_filter} if sources_filter else None
    sources = plan.sources
    if allowed:
        sources = tuple(source for source in plan.sources if source.value in allowed)
    for source in sources:
        try:
            rows = _fetch_by_source(
                source,
                duckdb_path=duckdb_path,
                series_id=plan.series_id,
                series_name=plan.series_name,
                vendor_series_code=vendor_series_code,
                frequency=plan.frequency,
                unit=plan.unit,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.warning(
                "macro backfill fetch failed series=%s source=%s error=%s",
                plan.series_name,
                source.value,
                exc,
            )
            continue
        if rows:
            return rows
    return []


def _filter_plan_sources(
    sources: tuple[BackfillSource, ...],
    allowed_sources: set[str] | None,
) -> tuple[BackfillSource, ...]:
    if allowed_sources is None:
        return sources
    return tuple(source for source in sources if source.value in allowed_sources)


def _fetch_by_source(
    source: BackfillSource,
    *,
    duckdb_path: Path,
    series_id: str,
    series_name: str,
    vendor_series_code: str,
    frequency: str,
    unit: str,
    start_date: str,
    end_date: str,
) -> list[BackfillRow]:
    if source == BackfillSource.CHOICE_SNAPSHOT:
        return _fetch_from_choice_snapshot(
            duckdb_path=duckdb_path,
            series_id=series_id,
            series_name=series_name,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    if source == BackfillSource.CHOICE_EDB:
        return _fetch_from_choice_edb(
            series_id=series_id,
            series_name=series_name,
            vendor_series_code=vendor_series_code,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    if source == BackfillSource.TUSHARE_MACRO:
        return _fetch_from_tushare(series_id=series_id, series_name=series_name, start_date=start_date, end_date=end_date, frequency=frequency, unit=unit)
    if source == BackfillSource.WIND:
        return _fetch_from_wind(
            series_id=series_id,
            series_name=series_name,
            vendor_series_code=vendor_series_code,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            unit=unit,
        )
    if source == BackfillSource.AKSHARE:
        return _fetch_from_akshare(series_id=series_id, series_name=series_name, start_date=start_date, end_date=end_date, frequency=frequency, unit=unit)
    return []


def _fetch_from_choice_snapshot(
    *,
    duckdb_path: Path,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        if not _relation_exists(conn, "choice_market_snapshot"):
            return []
        result = conn.execute(
            """
            select trade_date, value_numeric, frequency, unit
            from choice_market_snapshot
            where series_id = ? and trade_date between ? and ?
            order by trade_date
            """,
            [series_id, start_date, end_date],
        ).fetchall()
    finally:
        conn.close()
    rows: list[BackfillRow] = []
    for trade_date, value_numeric, row_frequency, row_unit in result:
        value = _coerce_float(value_numeric)
        normalized_date = normalize_trade_date(trade_date)
        if value is None or normalized_date is None:
            continue
        rows.append(
            BackfillRow(
                series_id=series_id,
                series_name=series_name,
                trade_date=normalized_date,
                value_numeric=value,
                frequency=str(row_frequency or frequency or "daily"),
                unit=str(row_unit or unit or "unknown"),
            )
        )
    return rows


def _fetch_from_choice_edb(
    *,
    series_id: str,
    series_name: str,
    vendor_series_code: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    from backend.scripts.backfill_cross_asset_macro_environment import (  # noqa: PLC0415
        SeriesMeta,
        choice_edb_rows,
    )

    client = ChoiceClient()
    request_options = f"IsLatest=0,StartDate={start_date},EndDate={end_date},Ispandas=1,RECVtimeout=20"
    result = client.edb([vendor_series_code], request_options)
    meta = SeriesMeta(
        series_id=series_id,
        series_name=series_name,
        vendor_name="choice",
        vendor_series_code=vendor_series_code,
        frequency=frequency,
        unit=unit,
        theme="macro_backfill",
        tags=("backfill",),
        refresh_tier="stable",
        request_options=request_options,
        fetch_mode="date_slice",
        fetch_granularity="batch",
        policy_note="macro_backfill choice edb",
    )
    parsed = choice_edb_rows(result, {vendor_series_code: meta})
    return [
        BackfillRow(
            series_id=str(row["series_id"]),
            series_name=str(row["series_name"]),
            trade_date=str(row["trade_date"]),
            value_numeric=float(row["value_numeric"]),
            frequency=str(row.get("frequency") or frequency),
            unit=str(row.get("unit") or unit),
        )
        for row in parsed
        if start_date <= str(row["trade_date"]) <= end_date
    ]


def _fetch_from_tushare(
    *,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    token = resolve_tushare_token_with_settings_fallback(get_settings())
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured.")

    ts = import_tushare_pro()
    pro = ts.pro_api(token)
    name = series_name

    if series_id.startswith("NCD.SHIBOR.") or "SHIBOR" in name.upper():
        time.sleep(0.3)
        return _tushare_shibor_rows(pro, series_id=series_id, series_name=series_name, start_date=start_date, end_date=end_date)

    tushare_api = _resolve_tushare_api(name)
    if tushare_api is None:
        return []

    request_start = _tushare_request_start_month(tushare_api, name, start_date)
    time.sleep(0.3)
    frame = {
        "cn_cpi": pro.cn_cpi,
        "cn_gdp": pro.cn_gdp,
        "cn_m": lambda: pro.cn_m(start_m=request_start, end_m=end_date[:7].replace("-", "")),
        "cn_pmi": lambda: pro.cn_pmi(start_m=request_start, end_m=end_date[:7].replace("-", "")),
        "sf_month": lambda: pro.sf_month(start_m=request_start, end_m=end_date[:7].replace("-", "")),
    }[tushare_api]()
    records = _records_from_frame(frame)
    mapped = _map_tushare_records(tushare_api, records, series_name=series_name)
    return [
        BackfillRow(
            series_id=series_id,
            series_name=series_name,
            trade_date=row["trade_date"],
            value_numeric=float(row["value"]),
            frequency=frequency,
            unit=unit,
        )
        for row in mapped
        if start_date <= row["trade_date"] <= end_date
    ]


def _tushare_shibor_rows(pro: Any, *, series_id: str, series_name: str, start_date: str, end_date: str) -> list[BackfillRow]:
    column_by_id = {
        "NCD.SHIBOR.1M": "1m",
        "NCD.SHIBOR.3M": "3m",
        "NCD.SHIBOR.6M": "6m",
        "NCD.SHIBOR.9M": "9m",
        "NCD.SHIBOR.1Y": "1y",
    }
    column = column_by_id.get(series_id)
    if column is None:
        match = re.search(r"SHIBOR:(\S+)", series_name, flags=re.IGNORECASE)
        column = {"1M": "1m", "3M": "3m", "6M": "6m", "9M": "9m", "1Y": "1y"}.get((match.group(1) if match else "").upper())
    if column is None:
        return []

    frame = pro.shibor(start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
    rows: list[BackfillRow] = []
    for record in _records_from_frame(frame):
        trade_date = normalize_trade_date(record.get("date"))
        value = _coerce_float(record.get(column))
        if trade_date is None or value is None:
            continue
        rows.append(
            BackfillRow(
                series_id=series_id,
                series_name=series_name,
                trade_date=trade_date,
                value_numeric=value,
                frequency="daily",
                unit="%",
            )
        )
    return rows


def _fetch_from_wind(
    *,
    series_id: str,
    series_name: str,
    vendor_series_code: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    if not _wind_available():
        raise RuntimeError("WindPy is not available.")

    from WindPy import w  # type: ignore  # noqa: PLC0415

    if w.isconnected() is False and w.start() != 0:
        raise RuntimeError("Wind start failed.")

    wind_code = vendor_series_code or series_id
    payload = w.wsd(wind_code, "close", start_date, end_date, "")
    if int(getattr(payload, "ErrorCode", -1)) != 0:
        raise RuntimeError(getattr(payload, "Data", f"Wind wsd failed for {wind_code}"))

    rows: list[BackfillRow] = []
    for trade_time, raw_value in zip(getattr(payload, "Times", []), (getattr(payload, "Data", [[]])[0] or []), strict=False):
        trade_date = normalize_trade_date(trade_time)
        value = _coerce_float(raw_value)
        if trade_date is None or value is None:
            continue
        rows.append(
            BackfillRow(
                series_id=series_id,
                series_name=series_name,
                trade_date=trade_date,
                value_numeric=value,
                frequency=frequency,
                unit=unit,
            )
        )
    return rows


def _fetch_from_akshare(
    *,
    series_id: str,
    series_name: str,
    start_date: str,
    end_date: str,
    frequency: str,
    unit: str,
) -> list[BackfillRow]:
    import akshare as ak  # type: ignore  # noqa: PLC0415

    if series_id == "CA.DR007" or "DR007" in series_name:
        records: list[dict[str, object]] = []
        for chunk_start, chunk_end in _month_ranges(start_date, end_date):
            frame = ak.repo_rate_hist(
                start_date=chunk_start.replace("-", ""),
                end_date=chunk_end.replace("-", ""),
            )
            records.extend(_records_from_frame(frame))
        rows: list[BackfillRow] = []
        for record in records:
            trade_date = normalize_trade_date(record.get("date"))
            value = _coerce_float(record.get("FDR007"))
            if trade_date is None or value is None or trade_date < start_date or trade_date > end_date:
                continue
            rows.append(
                BackfillRow(
                    series_id=series_id,
                    series_name=series_name,
                    trade_date=trade_date,
                    value_numeric=value,
                    frequency="daily",
                    unit="%",
                )
            )
        return rows

    if "螺纹" in series_name or series_id == "CA.STEEL":
        frame = ak.spot_price_qh(symbol="螺纹钢")
        rows = []
        for record in _records_from_frame(frame):
            trade_date = normalize_trade_date(record.get("日期"))
            value = _coerce_float(record.get("现货价格"))
            if trade_date is None or value is None or trade_date < start_date or trade_date > end_date:
                continue
            rows.append(
                BackfillRow(
                    series_id=series_id,
                    series_name=series_name,
                    trade_date=trade_date,
                    value_numeric=value,
                    frequency="daily",
                    unit="CNY/t",
                )
            )
        return rows

    return []


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[BackfillRow],
    source_version: str,
    vendor_version: str,
    run_id: str,
) -> int:
    if not rows:
        return 0
    added = 0
    conn.execute("begin transaction")
    try:
        for row in rows:
            exists = conn.execute(
                """
                select 1
                from fact_choice_macro_daily
                where series_id = ? and trade_date = ?
                limit 1
                """,
                [row.series_id, row.trade_date],
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                insert into fact_choice_macro_daily (
                  series_id,
                  series_name,
                  trade_date,
                  value_numeric,
                  frequency,
                  unit,
                  source_version,
                  vendor_version,
                  rule_version,
                  quality_flag,
                  run_id
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row.series_id,
                    row.series_name,
                    row.trade_date,
                    row.value_numeric,
                    row.frequency,
                    row.unit,
                    source_version,
                    vendor_version,
                    RULE_VERSION,
                    "ok",
                    run_id,
                ],
            )
            added += 1
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    return added


def _count_snapshot_rows(conn_path: Path, *, series_id: str, start_date: str, end_date: str) -> int:
    conn = duckdb.connect(str(conn_path), read_only=True)
    try:
        if not _relation_exists(conn, "choice_market_snapshot"):
            return 0
        row = conn.execute(
            """
            select count(*)
            from choice_market_snapshot
            where series_id = ? and trade_date between ? and ?
            """,
            [series_id, start_date, end_date],
        ).fetchone()
    finally:
        conn.close()
    return int(row[0] if row else 0)


def _relation_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select count(*)
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [table_name],
    ).fetchone()
    return bool(row and int(row[0]) > 0)


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _map_tushare_records(api: str, records: list[dict[str, object]], *, series_name: str) -> list[dict[str, object]]:
    if api == "sf_month" and _is_social_financing_stock_yoy_series(series_name):
        return _social_financing_stock_yoy_records(records)

    rows: list[dict[str, object]] = []
    for record in records:
        if api == "cn_cpi":
            trade_date = _month_to_trade_date(str(record.get("month") or ""))
            value = _pick_tushare_value(record, series_name, {"当月同比": "nt_yoy", "CPI": "nt_yoy"})
        elif api == "cn_gdp":
            trade_date = _quarter_to_trade_date(str(record.get("quarter") or ""))
            value = _pick_tushare_value(record, series_name, {"当季值": "gdp", "GDP": "gdp_yoy", "同比": "gdp_yoy"})
        elif api == "cn_m":
            trade_date = _month_to_trade_date(str(record.get("month") or ""))
            if "M1-M2" in series_name:
                m1_yoy = _coerce_float(record.get("m1_yoy"))
                m2_yoy = _coerce_float(record.get("m2_yoy"))
                value = (m1_yoy - m2_yoy) if m1_yoy is not None and m2_yoy is not None else None
            else:
                value = _pick_tushare_value(
                    record,
                    series_name,
                    {
                        "M0:环比": "m0_mom",
                        "M1:环比": "m1_mom",
                        "M2:环比": "m2_mom",
                        "M0:同比": "m0_yoy",
                        "M1:同比": "m1_yoy",
                        "M2:同比": "m2_yoy",
                        "M0": "m0",
                        "M1": "m1",
                        "M2": "m2",
                    },
                )
        elif api == "cn_pmi":
            trade_date = _month_to_trade_date(str(record.get("month") or record.get("MONTH") or ""))
            value = _pick_tushare_value(record, series_name, {"PMI": "pmi", "制造业": "pmi"})
        elif api == "sf_month":
            trade_date = _month_to_trade_date(str(record.get("month") or ""))
            value = _pick_tushare_value(record, series_name, {"社融": "inc_month", "社会融资": "inc_month"})
        else:
            continue
        if trade_date and value is not None:
            rows.append({"trade_date": trade_date, "value": float(value)})
    return rows


def _social_financing_stock_yoy_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    stock_by_month: dict[str, float] = {}
    for record in records:
        month = str(record.get("month") or "").strip()
        if len(month) != 6 or not month.isdigit():
            continue
        value = _coerce_float(record.get("stk_endval"))
        if value is None:
            continue
        stock_by_month[month] = value

    rows: list[dict[str, object]] = []
    for month in sorted(stock_by_month):
        previous_month = f"{int(month[:4]) - 1}{month[4:]}"
        previous_value = stock_by_month.get(previous_month)
        if previous_value is None or previous_value == 0:
            continue
        rows.append(
            {
                "trade_date": _month_to_trade_date(month),
                "value": (stock_by_month[month] / previous_value - 1) * 100,
            }
        )
    return rows


def _is_social_financing_stock_yoy_series(series_name: str) -> bool:
    return "社会融资规模存量" in series_name and "同比" in series_name


def _tushare_request_start_month(api: str, series_name: str, start_date: str) -> str:
    start_month = start_date[:7].replace("-", "")
    if api == "sf_month" and _is_social_financing_stock_yoy_series(series_name):
        return f"{int(start_month[:4]) - 1}{start_month[4:]}"
    return start_month


def _pick_tushare_value(record: dict[str, object], series_name: str, mapping: dict[str, str]) -> float | None:
    for needle, field in mapping.items():
        if needle in series_name:
            return _coerce_float(record.get(field))
    first_field = next(iter(mapping.values()), None)
    return _coerce_float(record.get(first_field)) if first_field else None


def _resolve_tushare_api(series_name: str) -> str | None:
    name = series_name
    if "CPI" in name:
        return "cn_cpi"
    if "GDP" in name:
        return "cn_gdp"
    if "广义货币M2/" in name:
        return None
    if re.search(r"^(M[012](:|$)|M[012]:|M1-M2)", name):
        return "cn_m"
    if "PMI" in name:
        return "cn_pmi"
    if "社融" in name or "社会融资" in name:
        return "sf_month"
    return None


def _is_commodity_series(series_name: str) -> bool:
    return any(token in series_name for token in ("现货", "螺纹", "Brent", "原油", "黄金", "铜", "商品"))


def _is_tushare_macro_series(series_name: str) -> bool:
    return _resolve_tushare_api(series_name) is not None


def _is_spread_series(series_name: str) -> bool:
    return "利差" in series_name


def _is_daily_rate_series(series_name: str, series_id: str) -> bool:
    upper = series_name.upper()
    if "SHIBOR" in upper or "DR007" in upper:
        return True
    if "国债" in series_name and "收益率" in series_name:
        return True
    if series_id in {"CA.DR007", "E1000180", "EMM00166466"}:
        return True
    return False


def _infer_frequency(series_name: str, catalog_frequency: str) -> str:
    if catalog_frequency and catalog_frequency != "unknown":
        return catalog_frequency
    if _resolve_tushare_api(series_name) == "cn_gdp":
        return "quarterly"
    if _resolve_tushare_api(series_name) in {"cn_cpi", "cn_m", "cn_pmi", "sf_month"}:
        return "monthly"
    if _is_daily_rate_series(series_name, ""):
        return "daily"
    return "unknown"


def _wind_available() -> bool:
    try:
        from WindPy import w  # type: ignore  # noqa: PLC0415, F401

        _ = w
        return True
    except Exception:
        return False


def _tushare_token_configured() -> bool:
    return bool(resolve_tushare_token_with_settings_fallback(get_settings()))


def _dedupe_sources(sources: list[BackfillSource]) -> list[BackfillSource]:
    seen: set[BackfillSource] = set()
    ordered: list[BackfillSource] = []
    for source in sources:
        if source in seen:
            continue
        seen.add(source)
        ordered.append(source)
    return ordered


def _validate_iso_date(value: str, *, field_name: str) -> None:
    date.fromisoformat(value)


def _month_to_trade_date(month: str) -> str | None:
    text = str(month or "").strip()
    if len(text) == 6 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-01"
    return normalize_trade_date(text)


def _quarter_to_trade_date(quarter: str) -> str | None:
    q = str(quarter or "").strip().upper()
    if len(q) >= 6 and "Q" in q:
        year = int(q[:4])
        qn = q[5:6]
        ends = {"1": "-03-31", "2": "-06-30", "3": "-09-30", "4": "-12-31"}
        if qn in ends:
            return f"{year}{ends[qn]}"
    return normalize_trade_date(q)


def normalize_trade_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    normalized = text.replace("/", "-")
    if len(normalized) >= 10 and normalized[4] == "-" and normalized[7] == "-":
        return normalized[:10]
    return normalized


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return float(text)


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


def _month_ranges(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    ranges: list[tuple[str, str]] = []
    current = start
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        chunk_end = min(end, next_month - timedelta(days=1))
        ranges.append((current.isoformat(), chunk_end.isoformat()))
        current = chunk_end + timedelta(days=1)
    return ranges


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill sparse macro series in DuckDB.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not fetch or insert.")
    parser.add_argument("--start-date", default="2024-01-01", help="Backfill window start (YYYY-MM-DD).")
    parser.add_argument("--end-date", default=None, help="Backfill window end (YYYY-MM-DD); defaults to today.")
    parser.add_argument(
        "--series-names",
        nargs="+",
        default=None,
        help="Optional series_name filter; omit to scan all sparse series.",
    )
    parser.add_argument(
        "--duckdb-path",
        default=str(_REPO_ROOT / "data" / "moss.duckdb"),
        help="Path to DuckDB file.",
    )
    args = parser.parse_args()
    payload = backfill_macro_series(
        duckdb_path=args.duckdb_path,
        series_names=args.series_names,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
