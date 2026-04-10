from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.schemas.macro_vendor import (
    ChoiceMacroLatestPayload,
    ChoiceMacroLatestPoint,
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
        tables = {
            row[0]
            for row in conn.execute("show tables").fetchall()
        }
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
        quality_flag=_quality_flag_for_series(payload.series),
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

        rows = conn.execute(
            """
            with ranked as (
              select
                series_id,
                series_name,
                trade_date,
                value_numeric,
                unit,
                source_version,
                vendor_version,
                row_number() over(partition by series_id order by trade_date desc) as rn
              from fact_choice_macro_daily
            )
            select series_id, series_name, trade_date, value_numeric, unit, source_version, vendor_version
            from ranked
            where rn = 1
            order by series_id
            """
        ).fetchall()
    except duckdb.Error:
        return ChoiceMacroLatestPayload(series=[])
    finally:
        conn.close()

    return ChoiceMacroLatestPayload(
        series=[
            ChoiceMacroLatestPoint(
                series_id=str(series_id),
                series_name=str(series_name),
                trade_date=str(trade_date),
                value_numeric=float(value_numeric),
                unit=str(unit),
                source_version=str(source_version),
                vendor_version=str(vendor_version),
            )
            for series_id, series_name, trade_date, value_numeric, unit, source_version, vendor_version in rows
        ]
    )


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
        quality_flag=_quality_flag_for_series(payload.series),
        scenario_flag=False,
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def _aggregate_lineage_value(values: list[str], empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)


def _quality_flag_for_series(series: list[object]) -> str:
    return "ok" if series else "warning"
