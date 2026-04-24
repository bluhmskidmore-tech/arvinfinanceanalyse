"""HTTP-safe series reads: route catalog ``view_name`` / ``std`` tables only (M2b)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb
from backend.app.schemas.external_data import ExternalDataCatalogEntry

# Exact physical/view names that may be queried (no user-controlled identifiers in SQL).
_ALLOWED_RELATIONS: frozenset[str] = frozenset(
    {
        "std_external_macro_daily",
        "std_external_supply_auction_calendar",
        "vw_external_macro_daily",
        "vw_external_legacy_choice_macro",
        "vw_external_legacy_choice_news",
        "vw_external_legacy_yield_curve",
        "vw_external_legacy_fx_mid",
        "vw_external_supply_auction_calendar",
    }
)

# Catalog ``series_id`` values that map to whole-table (umbrella) legacy surfaces.
_LEGACY_UMBRELLA_SERIES: frozenset[str] = frozenset(
    {
        "legacy.choice.macro",
        "legacy.choice.news",
        "legacy.akshare.yield_curve",
        "legacy.akshare.fx_mid",
    }
)


@dataclass
class SeriesDataPage:
    rows: list[dict[str, Any]]
    table_name: str
    limit: int
    offset: int


def _date_column_for_relation(relation: str) -> str:
    if relation in {
        "std_external_supply_auction_calendar",
        "vw_external_supply_auction_calendar",
    }:
        return "event_date"
    return "trade_date"


def _resolve_relation(entry: ExternalDataCatalogEntry) -> str:
    v = (entry.view_name or "").strip()
    t = (entry.standardized_table or "").strip()
    if v in _ALLOWED_RELATIONS:
        return v
    if t in _ALLOWED_RELATIONS:
        return t
    msg = f"series {entry.series_id!r} has no allowed view or std table in catalog"
    raise ValueError(msg)


def _is_umbrella(entry: ExternalDataCatalogEntry) -> bool:
    if entry.series_id not in _LEGACY_UMBRELLA_SERIES:
        return False
    rel = _resolve_relation(entry)
    return rel.startswith("vw_external_legacy_")


def _where_clause(
    entry: ExternalDataCatalogEntry,
    *,
    relation: str,
    recent_days: int | None,
) -> tuple[str, list[Any]]:
    date_column = _date_column_for_relation(relation)
    if _is_umbrella(entry):
        if recent_days is None:
            return "where 1=1", []
        d = max(1, min(recent_days, 3650))
        return f"where try_cast({date_column} as date) >= (current_date - ?::integer)", [d]
    if recent_days is None:
        return "where series_id = ?", [entry.series_id]
    d = max(1, min(recent_days, 3650))
    return (
        f"where series_id = ? and try_cast({date_column} as date) >= (current_date - ?::integer)",
        [entry.series_id, d],
    )


def _order_clause(relation: str) -> str:
    return f"order by {_date_column_for_relation(relation)} desc nulls last"


def fetch_series_data_page(
    conn: duckdb.DuckDBPyConnection,
    entry: ExternalDataCatalogEntry,
    *,
    limit: int = 100,
    offset: int = 0,
) -> SeriesDataPage:
    rel = _resolve_relation(entry)
    wsql, wparams = _where_clause(entry, relation=rel, recent_days=None)
    lim = max(1, min(limit, 10_000))
    off = max(0, offset)
    q = f"select * from {rel} {wsql} {_order_clause(rel)} limit ? offset ?"
    params: list[Any] = [*wparams, lim, off]
    res = conn.execute(q, params)
    rows = res.fetchall()
    cols = [d[0] for d in (res.description or [])]
    if not cols and not rows:
        cols = [d[0] for d in (conn.execute(f"select * from {rel} limit 0").description or [])]
    out = [_row_to_dict(cols, r) for r in rows]
    return SeriesDataPage(rows=out, table_name=rel, limit=lim, offset=off)


def _row_to_dict(cols: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}


def fetch_series_data_recent(
    conn: duckdb.DuckDBPyConnection,
    entry: ExternalDataCatalogEntry,
    *,
    days: int = 30,
    limit: int = 10_000,
) -> SeriesDataPage:
    d = max(1, min(days, 3650))
    rel = _resolve_relation(entry)
    wsql, wparams = _where_clause(entry, relation=rel, recent_days=d)
    q = f"select * from {rel} {wsql} {_order_clause(rel)} limit ?"
    cap = min(max(1, limit), 50_000)
    params = [*wparams, cap]
    res = conn.execute(q, params)
    rows = res.fetchall()
    cols = [d[0] for d in (res.description or [])]
    if not cols and not rows:
        cols = [d[0] for d in (conn.execute(f"select * from {rel} limit 0").description or [])]
    out = [_row_to_dict(cols, r) for r in rows]
    return SeriesDataPage(rows=out, table_name=rel, limit=len(out), offset=0)
