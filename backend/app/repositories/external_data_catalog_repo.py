"""DuckDB repository for ``external_data_catalog`` (does not read ``phase1_macro_vendor_catalog``).

Also owns the series watermark / paginated-read query implementations for the
external-data API surface (moved from ``external_data_query_service``, which
now only re-exports these names for backward-compatible imports).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal, TypeVar, cast

import duckdb
from backend.app.core_finance.data_freshness import FRESHNESS_TIER_UNKNOWN, assess_freshness
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.schemas.external_data import ExternalDataCatalogEntry

DomainLiteral = Literal["macro", "news", "yield_curve", "fx", "other"]

T = TypeVar("T")

# Series-read relations allowed for watermark / page helpers (exact physical/view
# names only; no user-controlled identifiers are ever interpolated into SQL).
RELATION_STD_EXTERNAL_MACRO_DAILY = "std_external_macro_daily"
RELATION_STD_EXTERNAL_SUPPLY_AUCTION_CALENDAR = "std_external_supply_auction_calendar"
RELATION_VW_EXTERNAL_MACRO_DAILY = "vw_external_macro_daily"
RELATION_VW_EXTERNAL_LEGACY_CHOICE_MACRO = "vw_external_legacy_choice_macro"
RELATION_VW_EXTERNAL_LEGACY_CHOICE_NEWS = "vw_external_legacy_choice_news"
RELATION_VW_EXTERNAL_LEGACY_YIELD_CURVE = "vw_external_legacy_yield_curve"
RELATION_VW_EXTERNAL_LEGACY_FX_MID = "vw_external_legacy_fx_mid"
RELATION_VW_EXTERNAL_SUPPLY_AUCTION_CALENDAR = "vw_external_supply_auction_calendar"

_EXTERNAL_DATA_SERIES_READ_RELATIONS = frozenset(
    {
        RELATION_STD_EXTERNAL_MACRO_DAILY,
        RELATION_STD_EXTERNAL_SUPPLY_AUCTION_CALENDAR,
        RELATION_VW_EXTERNAL_MACRO_DAILY,
        RELATION_VW_EXTERNAL_LEGACY_CHOICE_MACRO,
        RELATION_VW_EXTERNAL_LEGACY_CHOICE_NEWS,
        RELATION_VW_EXTERNAL_LEGACY_YIELD_CURVE,
        RELATION_VW_EXTERNAL_LEGACY_FX_MID,
        RELATION_VW_EXTERNAL_SUPPLY_AUCTION_CALENDAR,
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


@dataclass(frozen=True)
class SeriesWatermark:
    relation_name: str
    date_column: str
    row_count: int
    latest_business_date: str | None
    latest_loaded_at: str | None
    # Calendar-day age of latest_business_date relative to the as-of date
    # (date.today() unless the caller pins one) and the shared freshness tier.
    age_days: int | None = None
    freshness_tier: str | None = None


# Catalog ``frequency`` spellings that map onto the shared freshness cadences.
# Anything else (quarterly, event, unknown, None) gets tier "unknown" instead
# of being misjudged against daily thresholds.
_CADENCE_BY_CATALOG_FREQUENCY: dict[str, str] = {
    "d": "daily",
    "day": "daily",
    "daily": "daily",
    "w": "weekly",
    "week": "weekly",
    "weekly": "weekly",
    "m": "monthly",
    "month": "monthly",
    "monthly": "monthly",
}


def _cadence_from_catalog_frequency(frequency: str | None) -> str | None:
    if frequency is None:
        return None
    return _CADENCE_BY_CATALOG_FREQUENCY.get(str(frequency).strip().lower())


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
    if v in _EXTERNAL_DATA_SERIES_READ_RELATIONS:
        return v
    if t in _EXTERNAL_DATA_SERIES_READ_RELATIONS:
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


def _value_to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _loaded_column_for_relation(conn: duckdb.DuckDBPyConnection, relation: str) -> str | None:
    desc = conn.execute(f"select * from {relation} limit 0").description or []
    columns = {str(d[0]) for d in desc}
    if "created_at" in columns:
        return "created_at"
    if "received_at" in columns:
        return "received_at"
    return None


def _row_to_dict(cols: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}


def fetch_series_watermark(
    conn: duckdb.DuckDBPyConnection,
    entry: ExternalDataCatalogEntry,
    *,
    as_of_date: date | None = None,
) -> SeriesWatermark:
    rel = _resolve_relation(entry)
    date_column = _date_column_for_relation(rel)
    loaded_column = _loaded_column_for_relation(conn, rel)
    loaded_expr = (
        f"max(cast({loaded_column} as varchar))"
        if loaded_column is not None
        else "cast(null as varchar)"
    )
    wsql, wparams = _where_clause(entry, relation=rel, recent_days=None)
    res = conn.execute(
        f"""
        select
          count(*)::bigint as row_count,
          max(try_cast({date_column} as date)) as latest_business_date,
          {loaded_expr} as latest_loaded_at
        from {rel}
        {wsql}
        """,
        wparams,
    )
    row = res.fetchone() or (0, None, None)
    latest_business_date = _value_to_text(row[1])
    as_of = as_of_date if as_of_date is not None else date.today()
    cadence = _cadence_from_catalog_frequency(entry.frequency)
    assessment = assess_freshness(latest_business_date, as_of, cadence=cadence or "daily")
    return SeriesWatermark(
        relation_name=rel,
        date_column=date_column,
        row_count=int(row[0] or 0),
        latest_business_date=latest_business_date,
        latest_loaded_at=_value_to_text(row[2]),
        age_days=assessment.age_days,
        freshness_tier=assessment.tier if cadence is not None else FRESHNESS_TIER_UNKNOWN,
    )


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


def ensure_external_data_catalog_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply ``14_external_data_catalog.sql`` DDL on the connection."""
    text = (REGISTRY_DIR / "14_external_data_catalog.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


class ExternalDataCatalogRepository:
    """CRUD for ``external_data_catalog``; upsert keyed by ``series_id``.

    Also owns read-only series watermark / page connections for the external-data
    API surface, backed by the module-level ``fetch_series_*`` query functions
    above. Series relation names are gated by ``_EXTERNAL_DATA_SERIES_READ_RELATIONS``.
    """

    SERIES_READ_RELATIONS = _EXTERNAL_DATA_SERIES_READ_RELATIONS

    def __init__(
        self,
        *,
        path: str | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        if (path is None) == (conn is None):
            msg = "Exactly one of path= or conn= must be provided."
            raise ValueError(msg)
        self._path = path
        self._conn = conn

    @contextmanager
    def _connection(self, *, read_only: bool):
        if self._conn is not None:
            yield self._conn
            return
        path = self._path or ":memory:"
        c = duckdb.connect(path) if path == ":memory:" else duckdb.connect(path, read_only=read_only)
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def _series_read_connection(
        self,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open (or reuse) a read-only connection for series watermark/page queries."""
        if conn is not None:
            yield conn
            return
        if self._conn is not None:
            yield self._conn
            return
        if self._path is None:
            msg = "path= or conn= is required for external data series reads"
            raise RuntimeError(msg)
        with read_only_connection(self._path) as scoped:
            yield scoped

    def _run_series_read(
        self,
        fn: Callable[[duckdb.DuckDBPyConnection], T],
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> T:
        with self._series_read_connection(conn) as scoped:
            return fn(scoped)
    @staticmethod
    def _ts_to_iso(value: object) -> str:
        if isinstance(value, datetime):
            dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.isoformat()
        return str(value)

    @classmethod
    def _row_to_entry(cls, row: tuple[object, ...]) -> ExternalDataCatalogEntry:
        (
            series_id,
            series_name,
            vendor_name,
            source_family,
            domain,
            frequency,
            unit,
            refresh_tier,
            fetch_mode,
            raw_zone_path,
            standardized_table,
            view_name,
            access_path,
            catalog_version,
            created_at,
        ) = row
        return ExternalDataCatalogEntry(
            series_id=str(series_id),
            series_name=str(series_name),
            vendor_name=str(vendor_name),
            source_family=str(source_family),
            domain=cast(DomainLiteral, str(domain)),
            frequency=None if frequency is None else str(frequency),
            unit=None if unit is None else str(unit),
            refresh_tier=None if refresh_tier is None else str(refresh_tier),
            fetch_mode=None if fetch_mode is None else str(fetch_mode),
            raw_zone_path=None if raw_zone_path is None else str(raw_zone_path),
            standardized_table=None if standardized_table is None else str(standardized_table),
            view_name=None if view_name is None else str(view_name),
            access_path=None if access_path is None else str(access_path),
            catalog_version=str(catalog_version),
            created_at=cls._ts_to_iso(created_at),
        )

    def register(self, entry: ExternalDataCatalogEntry) -> ExternalDataCatalogEntry:
        require_repository_task_write_scope("ExternalDataCatalogRepository.register")
        sql = """
            insert or replace into external_data_catalog (
              series_id, series_name, vendor_name, source_family, domain,
              frequency, unit, refresh_tier, fetch_mode,
              raw_zone_path, standardized_table, view_name, access_path,
              catalog_version, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params: list[object] = [
            entry.series_id,
            entry.series_name,
            entry.vendor_name,
            entry.source_family,
            entry.domain,
            entry.frequency,
            entry.unit,
            entry.refresh_tier,
            entry.fetch_mode,
            entry.raw_zone_path,
            entry.standardized_table,
            entry.view_name,
            entry.access_path,
            entry.catalog_version,
            entry.created_at,
        ]
        with self._connection(read_only=False) as conn:
            conn.execute(sql, params)
        return entry

    def list_all(self) -> list[ExternalDataCatalogEntry]:
        sql = """
            select series_id, series_name, vendor_name, source_family, domain,
                   frequency, unit, refresh_tier, fetch_mode,
                   raw_zone_path, standardized_table, view_name, access_path,
                   catalog_version, created_at
            from external_data_catalog
            order by series_id
        """
        with self._connection(read_only=True) as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_entry(tuple(r)) for r in rows]

    def get_by_series_id(self, series_id: str) -> ExternalDataCatalogEntry | None:
        sql = """
            select series_id, series_name, vendor_name, source_family, domain,
                   frequency, unit, refresh_tier, fetch_mode,
                   raw_zone_path, standardized_table, view_name, access_path,
                   catalog_version, created_at
            from external_data_catalog
            where series_id = ?
            limit 1
        """
        with self._connection(read_only=True) as conn:
            row = conn.execute(sql, [series_id]).fetchone()
        if row is None:
            return None
        return self._row_to_entry(tuple(row))

    def list_by_domain(self, domain: str) -> list[ExternalDataCatalogEntry]:
        sql = """
            select series_id, series_name, vendor_name, source_family, domain,
                   frequency, unit, refresh_tier, fetch_mode,
                   raw_zone_path, standardized_table, view_name, access_path,
                   catalog_version, created_at
            from external_data_catalog
            where domain = ?
            order by series_id
        """
        with self._connection(read_only=True) as conn:
            rows = conn.execute(sql, [domain]).fetchall()
        return [self._row_to_entry(tuple(r)) for r in rows]

    def fetch_series_watermark(
        self,
        entry: ExternalDataCatalogEntry,
        *,
        as_of_date: date | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ):
        """Read one series watermark via shared read-only connection helpers."""
        return self._run_series_read(
            lambda scoped: fetch_series_watermark(scoped, entry, as_of_date=as_of_date),
            conn=conn,
        )

    def fetch_series_watermarks(
        self,
        entries: list[ExternalDataCatalogEntry],
        *,
        as_of_date: date | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[object]:
        """Fetch watermarks for many catalog entries on one connection.

        Each result is either a ``SeriesWatermark`` or an exception instance
        (``duckdb.Error`` / ``ValueError``), matching prior service semantics.
        """

        def _impl(scoped: duckdb.DuckDBPyConnection) -> list[object]:
            results: list[object] = []
            for entry in entries:
                try:
                    results.append(
                        fetch_series_watermark(scoped, entry, as_of_date=as_of_date)
                    )
                except (duckdb.Error, ValueError) as exc:
                    results.append(exc)
            return results

        return self._run_series_read(_impl, conn=conn)

    def fetch_series_data_page(
        self,
        entry: ExternalDataCatalogEntry,
        *,
        limit: int = 100,
        offset: int = 0,
        conn: duckdb.DuckDBPyConnection | None = None,
    ):
        """Paginated series rows via shared read-only connection helpers."""
        return self._run_series_read(
            lambda scoped: fetch_series_data_page(
                scoped, entry, limit=limit, offset=offset
            ),
            conn=conn,
        )

    def fetch_series_data_recent(
        self,
        entry: ExternalDataCatalogEntry,
        *,
        days: int = 30,
        limit: int = 10_000,
        conn: duckdb.DuckDBPyConnection | None = None,
    ):
        """Recent-window series rows via shared read-only connection helpers."""
        return self._run_series_read(
            lambda scoped: fetch_series_data_recent(
                scoped, entry, days=days, limit=limit
            ),
            conn=conn,
        )
