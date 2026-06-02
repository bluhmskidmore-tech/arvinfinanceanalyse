from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb

from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RESULT_KIND = "market_data.livermore.stock_detail"
RULE_VERSION = "rv_livermore_stock_detail_v1"
CACHE_VERSION = "cv_livermore_stock_detail_v1"
EMPTY_SOURCE_VERSION = "sv_livermore_stock_detail_empty"
EMPTY_VENDOR_VERSION = "vv_none"

TABLE_OBS = "choice_stock_daily_observation"
TABLE_FACTOR = "choice_stock_factor_snapshot"


def livermore_stock_detail_envelope(
    *,
    duckdb_path: str,
    stock_code: str,
    as_of_date: date | None,
    lookback: int,
) -> dict[str, object]:
    """Assemble OHLCV + factor snapshot for a single stock; read-only DuckDB SELECT only."""
    requested_iso = None if as_of_date is None else as_of_date.isoformat()
    empty_factor: dict[str, object] = {
        "as_of_date": None,
        "pe": None,
        "pb": None,
        "roe": None,
        "dividend_yield": None,
    }

    path = Path(duckdb_path)
    if not path.is_file():
        return _missing_envelope(
            stock_code=stock_code,
            requested_as_of_date=requested_iso,
            lookback=lookback,
            empty_factor=empty_factor,
        )

    conn = duckdb.connect(str(path), read_only=True)
    try:
        end_bound = _resolve_end_trade_date(conn, stock_code=stock_code, as_of_date=as_of_date)
        if end_bound is None:
            return _missing_envelope(
                stock_code=stock_code,
                requested_as_of_date=requested_iso,
                lookback=lookback,
                empty_factor=empty_factor,
            )

        candle_rows = _fetch_candles(
            conn,
            stock_code=stock_code,
            end_trade_date=end_bound,
            lookback=lookback,
        )
        factor_row = _fetch_factor_row(
            conn,
            stock_code=stock_code,
            end_as_of=end_bound.isoformat(),
        )
    finally:
        conn.close()

    if not candle_rows:
        return _missing_envelope(
            stock_code=stock_code,
            requested_as_of_date=requested_iso,
            lookback=lookback,
            resolved_as_of_date=end_bound.isoformat(),
            empty_factor=empty_factor,
        )

    candles = [_normalize_candle_row(row) for row in reversed(candle_rows)]
    factor_payload, fac_src, fac_vend = _normalize_factor_row(factor_row)

    lineage_src = _first_non_empty(
        *[c.get("source_version") for c in candles],
        fac_src,
        default=EMPTY_SOURCE_VERSION,
    )
    lineage_vend = _first_non_empty(
        *[c.get("vendor_version") for c in candles],
        fac_vend,
        default=EMPTY_VENDOR_VERSION,
    )
    for c in candles:
        c.pop("source_version", None)
        c.pop("vendor_version", None)

    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": "ok",
        "stock_code": stock_code,
        "requested_as_of_date": requested_iso,
        "as_of_date": end_bound.isoformat(),
        "lookback": lookback,
        "candles": candles,
        "factor": factor_payload,
    }

    evidence_rows = len(candles) + (1 if factor_row else 0)

    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_stock_detail_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=str(lineage_src),
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "ok"),
        vendor_version=str(lineage_vend),
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": requested_iso,
            "as_of_date": end_bound.isoformat(),
            "stock_code": stock_code,
            "lookback": lookback,
        },
        tables_used=[TABLE_OBS, TABLE_FACTOR],
        evidence_rows=evidence_rows,
        result_payload=result_payload,
    )


def _missing_envelope(
    *,
    stock_code: str,
    requested_as_of_date: str | None,
    lookback: int,
    empty_factor: dict[str, object],
    resolved_as_of_date: str | None = None,
) -> dict[str, object]:
    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": "missing",
        "stock_code": stock_code,
        "requested_as_of_date": requested_as_of_date,
        "as_of_date": resolved_as_of_date,
        "lookback": lookback,
        "candles": [],
        "factor": empty_factor,
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_stock_detail_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": requested_as_of_date,
            "as_of_date": resolved_as_of_date,
            "stock_code": stock_code,
            "lookback": lookback,
        },
        tables_used=[TABLE_OBS, TABLE_FACTOR],
        evidence_rows=0,
        result_payload=result_payload,
    )


def _resolve_end_trade_date(conn: duckdb.DuckDBPyConnection, *, stock_code: str, as_of_date: date | None) -> date | None:
    if as_of_date is not None:
        row = conn.execute(
            """
            select max(trade_date) as mx
            from choice_stock_daily_observation
            where stock_code = ?
              and trade_date <= ?
            """,
            [stock_code, as_of_date.isoformat()],
        ).fetchone()
    else:
        row = conn.execute(
            """
            select max(trade_date) as mx
            from choice_stock_daily_observation
            where stock_code = ?
            """,
            [stock_code],
        ).fetchone()
    if row is None or row[0] is None:
        return None
    raw = str(row[0]).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _fetch_candles(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    end_trade_date: date,
    lookback: int,
) -> list[dict[str, Any]]:
    upper = end_trade_date.isoformat()
    result = conn.execute(
        f"""
        select
          trade_date,
          open_value,
          high_value,
          low_value,
          close_value,
          volume,
          amount,
          source_version,
          vendor_version
        from {TABLE_OBS}
        where stock_code = ?
          and trade_date <= ?
        order by trade_date desc
        limit ?
        """,
        [stock_code, upper, lookback],
    )
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]


def _fetch_factor_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    end_as_of: str,
) -> dict[str, Any] | None:
    result = conn.execute(
        f"""
        select
          as_of_date,
          pe,
          pb,
          roe,
          dividend_yield,
          source_version,
          vendor_version
        from {TABLE_FACTOR}
        where stock_code = ?
          and as_of_date <= ?
        order by as_of_date desc
        limit 1
        """,
        [stock_code, end_as_of],
    )
    row = result.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in result.description]
    return dict(zip(cols, row, strict=True))


def _normalize_candle_row(row: dict[str, Any]) -> dict[str, object]:
    return {
        "trade_date": str(row.get("trade_date") or "").strip()[:10],
        "open_value": _maybe_float(row.get("open_value")),
        "high_value": _maybe_float(row.get("high_value")),
        "low_value": _maybe_float(row.get("low_value")),
        "close_value": _maybe_float(row.get("close_value")),
        "volume": _maybe_float(row.get("volume")),
        "amount": _maybe_float(row.get("amount")),
        "source_version": _optional_str(row.get("source_version")),
        "vendor_version": _optional_str(row.get("vendor_version")),
    }


def _normalize_factor_row(
    row: dict[str, Any] | None,
) -> tuple[dict[str, object], str | None, str | None]:
    if row is None:
        return (
            {
                "as_of_date": None,
                "pe": None,
                "pb": None,
                "roe": None,
                "dividend_yield": None,
            },
            None,
            None,
        )
    as_of = row.get("as_of_date")
    as_of_s = str(as_of).strip()[:10] if as_of is not None else None
    if as_of_s == "":
        as_of_s = None
    return (
        {
            "as_of_date": as_of_s,
            "pe": _maybe_float(row.get("pe")),
            "pb": _maybe_float(row.get("pb")),
            "roe": _maybe_float(row.get("roe")),
            "dividend_yield": _maybe_float(row.get("dividend_yield")),
        },
        _optional_str(row.get("source_version")),
        _optional_str(row.get("vendor_version")),
    )


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_non_empty(*values: object, default: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default
