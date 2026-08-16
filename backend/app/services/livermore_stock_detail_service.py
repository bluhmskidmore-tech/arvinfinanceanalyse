from __future__ import annotations

import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any, cast

from backend.app.repositories.livermore_market_read_repo import (
    TABLE_FACTOR,
    TABLE_OBS,
    LivermoreMarketReadRepository,
)
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

logger = logging.getLogger(__name__)

RESULT_KIND = "market_data.livermore.stock_detail"
RULE_VERSION = "rv_livermore_stock_detail_v1"
CACHE_VERSION = "cv_livermore_stock_detail_v1"
EMPTY_SOURCE_VERSION = "sv_livermore_stock_detail_empty"
EMPTY_VENDOR_VERSION = "vv_none"


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

    repo = LivermoreMarketReadRepository(str(path))
    with repo.scoped_connection() as conn:
        if conn is None:
            return _missing_envelope(
                stock_code=stock_code,
                requested_as_of_date=requested_iso,
                lookback=lookback,
                empty_factor=empty_factor,
            )
        end_bound = repo.resolve_stock_end_trade_date(
            stock_code=stock_code,
            as_of_date=as_of_date,
            conn=conn,
        )
        if end_bound is None:
            return _missing_envelope(
                stock_code=stock_code,
                requested_as_of_date=requested_iso,
                lookback=lookback,
                empty_factor=empty_factor,
            )

        candle_rows, unit_warnings = repo.fetch_candles(
            stock_code=stock_code,
            end_trade_date=end_bound,
            lookback=lookback,
            conn=conn,
        )
        factor_row = repo.fetch_factor_row(
            stock_code=stock_code,
            end_as_of=end_bound.isoformat(),
            conn=conn,
        )

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

    if unit_warnings:
        logger.warning(
            "livermore stock-detail unit warnings for %s: %s",
            stock_code,
            "; ".join(unit_warnings),
        )

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
        quality_flag=cast(QualityFlag, "warning" if unit_warnings else "ok"),
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
