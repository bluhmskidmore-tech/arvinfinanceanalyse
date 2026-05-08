from __future__ import annotations

import math
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import duckdb

from backend.app.core_finance.livermore_sector_rank import (
    SectorRankConstituent,
    compute_sector_rank,
)
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RESULT_KIND = "market_data.livermore.sector_rank_series"
RULE_VERSION = "rv_livermore_sector_rank_series_v1"
CACHE_VERSION = "cv_livermore_sector_rank_series_v1"
FORMULA_VERSION = "rv_livermore_sector_rank_series_v1"
EMPTY_SOURCE_VERSION = "sv_livermore_sector_rank_series_empty"
EMPTY_VENDOR_VERSION = "vv_none"

UNSUPPORTED_NOTES = (
    "momentum_persistence: needs metric definition review (P1)",
    "sector_money_flow: needs vendor approval & new schema (P1)",
)

TABLE_MEMBERSHIP = "choice_stock_sector_membership"
TABLE_OBS = "choice_stock_daily_observation"


def livermore_sector_rank_series_envelope(
    *,
    duckdb_path: str,
    as_of_date: date | None,
    window_days: int,
    sector_code: str | None,
    top_k: int,
) -> dict[str, object]:
    """Read-only multi-day sector rank series; reuses compute_sector_rank per trade_date."""
    sector_filter = sector_code.strip() if sector_code and str(sector_code).strip() else None
    path = Path(duckdb_path)
    if not path.is_file():
        return _missing_envelope(
            as_of_date_resolved=None,
            window_days=window_days,
            top_k=top_k,
            sector_code_filter=sector_filter,
        )

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        required = {TABLE_MEMBERSHIP, TABLE_OBS}
        if not required.issubset(tables):
            return _missing_envelope(
                as_of_date_resolved=None,
                window_days=window_days,
                top_k=top_k,
                sector_code_filter=sector_filter,
            )

        end_bound = _resolve_global_end_trade_date(conn, as_of_date=as_of_date)
        if end_bound is None:
            return _missing_envelope(
                as_of_date_resolved=None,
                window_days=window_days,
                top_k=top_k,
                sector_code_filter=sector_filter,
            )

        cal_span = int(math.ceil(window_days * 1.5))
        cal_start = end_bound - timedelta(days=cal_span)
        trade_dates = _fetch_trade_dates_in_range(
            conn,
            end_inclusive=end_bound,
            start_inclusive=cal_start,
            limit_last_n=window_days,
        )
        if not trade_dates:
            return _missing_envelope(
                as_of_date_resolved=end_bound.isoformat(),
                window_days=window_days,
                top_k=top_k,
                sector_code_filter=sector_filter,
            )

        daily_results: list[tuple[date, dict[str, Any], list[str], list[str]]] = []
        source_versions: list[str] = []
        vendor_versions: list[str] = []
        evidence_rows = 0

        for td in trade_dates:
            iso = td.isoformat()
            rows, srcs, vends = _load_sector_rank_constituents(conn, as_of_date=iso)
            evidence_rows += len(rows)
            source_versions.extend(srcs)
            vendor_versions.extend(vends)
            result = compute_sector_rank(as_of_date=iso, rows=rows)
            if not result.ready or result.payload is None:
                continue
            daily_results.append((td, cast(dict[str, Any], result.payload), srcs, vends))

        if not daily_results:
            return _missing_envelope(
                as_of_date_resolved=end_bound.isoformat(),
                window_days=window_days,
                top_k=top_k,
                sector_code_filter=sector_filter,
            )

        latest_td, latest_payload, _, _ = daily_results[-1]
        items_raw = latest_payload.get("items")
        if not isinstance(items_raw, list):
            return _missing_envelope(
                as_of_date_resolved=latest_td.isoformat(),
                window_days=window_days,
                top_k=top_k,
                sector_code_filter=sector_filter,
            )

        latest_items = cast(list[dict[str, Any]], items_raw)
        if sector_filter is not None:
            selected_codes: set[str] = {sector_filter}
        else:
            selected_codes = {
                str(it.get("sector_code") or "").strip()
                for it in latest_items[:top_k]
                if str(it.get("sector_code") or "").strip()
            }

        by_date_item: dict[tuple[str, str], dict[str, Any]] = {}
        for td, payload, _, _ in daily_results:
            day_items = payload.get("items")
            if not isinstance(day_items, list):
                continue
            for it in cast(list[dict[str, Any]], day_items):
                code = str(it.get("sector_code") or "").strip()
                if code not in selected_codes:
                    continue
                name = str(it.get("sector_name") or "").strip()
                by_date_item[(td.isoformat(), code)] = it

        cum_by_sector: dict[str, float] = {c: 0.0 for c in selected_codes}
        for td, payload, _, _ in daily_results:
            day_items = payload.get("items")
            if not isinstance(day_items, list):
                continue
            for it in cast(list[dict[str, Any]], day_items):
                code = str(it.get("sector_code") or "").strip()
                if code not in selected_codes:
                    continue
                apc = it.get("avg_pctchange")
                if isinstance(apc, (int, float)) and math.isfinite(float(apc)):
                    cum_by_sector[code] += float(apc)

        latest_iso = latest_td.isoformat()
        series: list[dict[str, object]] = []
        for td, _, _, _ in daily_results:
            d_iso = td.isoformat()
            for code in sorted(selected_codes):
                it = by_date_item.get((d_iso, code))
                if it is None:
                    continue
                name = str(it.get("sector_name") or "").strip()
                cum_val: float | None = None
                if d_iso == latest_iso:
                    cum_val = round(cum_by_sector.get(code, 0.0), 6)
                series.append(
                    {
                        "trade_date": d_iso,
                        "sector_code": code,
                        "sector_name": name,
                        "score": _item_float(it.get("score")),
                        "rank": _item_int(it.get("rank")),
                        "avg_pctchange": _item_float(it.get("avg_pctchange")),
                        "avg_turn": _item_float(it.get("avg_turn")),
                        "avg_amplitude": _item_float(it.get("avg_amplitude")),
                        "constituent_count": _item_int(it.get("constituent_count")),
                        "cum_pctchange_window": cum_val,
                    }
                )

        lineage_src = _aggregate_lineage(source_versions, empty_value=EMPTY_SOURCE_VERSION)
        lineage_vend = _aggregate_lineage(vendor_versions, empty_value=EMPTY_VENDOR_VERSION)

        result_payload: dict[str, object] = {
            "basis": "analytical",
            "state": "ok",
            "as_of_date": latest_iso,
            "window_days": window_days,
            "top_k": top_k,
            "sector_code_filter": sector_filter,
            "formula_version": FORMULA_VERSION,
            "series": series,
            "unsupported_notes": list(UNSUPPORTED_NOTES),
        }

        return build_result_envelope(
            basis="analytical",
            trace_id=f"tr_livermore_sector_rank_series_{uuid.uuid4().hex[:12]}",
            result_kind=RESULT_KIND,
            cache_version=CACHE_VERSION,
            source_version=lineage_src,
            rule_version=RULE_VERSION,
            quality_flag=cast(QualityFlag, "ok"),
            vendor_version=lineage_vend,
            vendor_status=cast(VendorStatus, "ok"),
            fallback_mode=cast(FallbackMode, "none"),
            filters_applied={
                "requested_as_of_date": None if as_of_date is None else as_of_date.isoformat(),
                "as_of_date": latest_iso,
                "window_days": window_days,
                "top_k": top_k,
                "sector_code": sector_filter,
            },
            tables_used=[TABLE_MEMBERSHIP, TABLE_OBS],
            evidence_rows=evidence_rows,
            result_payload=result_payload,
        )
    finally:
        conn.close()


def _missing_envelope(
    *,
    as_of_date_resolved: str | None,
    window_days: int,
    top_k: int,
    sector_code_filter: str | None,
) -> dict[str, object]:
    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": "missing",
        "as_of_date": as_of_date_resolved,
        "window_days": window_days,
        "top_k": top_k,
        "sector_code_filter": sector_code_filter,
        "formula_version": FORMULA_VERSION,
        "series": [],
        "unsupported_notes": list(UNSUPPORTED_NOTES),
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_sector_rank_series_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": None,
            "as_of_date": as_of_date_resolved,
            "window_days": window_days,
            "top_k": top_k,
            "sector_code": sector_code_filter,
        },
        tables_used=[TABLE_MEMBERSHIP, TABLE_OBS],
        evidence_rows=0,
        result_payload=result_payload,
    )


def _resolve_global_end_trade_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    as_of_date: date | None,
) -> date | None:
    if as_of_date is not None:
        row = conn.execute(
            f"""
            select max(cast(trade_date as date)) as mx
            from {TABLE_OBS}
            where cast(trade_date as date) <= cast(? as date)
            """,
            [as_of_date.isoformat()],
        ).fetchone()
    else:
        row = conn.execute(
            f"""
            select max(cast(trade_date as date)) as mx
            from {TABLE_OBS}
            """,
        ).fetchone()
    if row is None or row[0] is None:
        return None
    raw = row[0]
    if hasattr(raw, "isoformat"):
        return cast(date, raw)
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _fetch_trade_dates_in_range(
    conn: duckdb.DuckDBPyConnection,
    *,
    end_inclusive: date,
    start_inclusive: date,
    limit_last_n: int,
) -> list[date]:
    rows = conn.execute(
        f"""
        select distinct cast(trade_date as date) as d
        from {TABLE_OBS}
        where cast(trade_date as date) <= ?
          and cast(trade_date as date) >= ?
        order by d desc
        """,
        [end_inclusive.isoformat(), start_inclusive.isoformat()],
    ).fetchall()
    out: list[date] = []
    for row in rows:
        if row[0] is None:
            continue
        raw = row[0]
        if hasattr(raw, "isoformat"):
            d = cast(date, raw)
        else:
            try:
                d = date.fromisoformat(str(raw).strip()[:10])
            except ValueError:
                continue
        out.append(d)
        if len(out) >= limit_last_n:
            break
    return list(reversed(out))


def _load_sector_rank_constituents(
    conn: duckdb.DuckDBPyConnection,
    *,
    as_of_date: str,
) -> tuple[list[SectorRankConstituent], list[str], list[str]]:
    try:
        rows = conn.execute(
            f"""
            select
              membership.stock_code,
              membership.sw2021code,
              membership.sw2021,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version
            from {TABLE_MEMBERSHIP} membership
            join {TABLE_OBS} daily
              on daily.stock_code = membership.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            where membership.as_of_date = ?
            """,
            [as_of_date, as_of_date],
        ).fetchall()
    except duckdb.Error:
        return [], [], []

    constituents = [
        SectorRankConstituent(
            stock_code=str(row[0] or ""),
            sector_code=str(row[1] or ""),
            sector_name=str(row[2] or ""),
            pctchange=row[3],
            turn=row[4],
            amplitude=row[5],
        )
        for row in rows
    ]
    source_versions = [str(value) for row in rows for value in (row[6], row[8]) if value]
    vendor_versions = [str(value) for row in rows for value in (row[7], row[9]) if value]
    return constituents, source_versions, vendor_versions


def _item_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _item_int(value: object) -> int | None:
    f = _item_float(value)
    return None if f is None else int(f)


def _aggregate_lineage(values: list[str], *, empty_value: str) -> str:
    distinct = sorted({value for value in values if value})
    if not distinct:
        return empty_value
    if len(distinct) == 1:
        return distinct[0]
    return "__".join(distinct)
