"""DuckDB repository for ``external_data_catalog`` (does not read ``phase1_macro_vendor_catalog``)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Literal, cast

import duckdb
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.schemas.external_data import ExternalDataCatalogEntry

DomainLiteral = Literal["macro", "news", "yield_curve", "fx", "other"]


def ensure_external_data_catalog_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply ``14_external_data_catalog.sql`` DDL on the connection."""
    text = (REGISTRY_DIR / "14_external_data_catalog.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


class ExternalDataCatalogRepository:
    """CRUD for ``external_data_catalog``; upsert keyed by ``series_id``."""

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
    def _connection(self):
        if self._conn is not None:
            yield self._conn
            return
        c = duckdb.connect(self._path or ":memory:")
        try:
            yield c
        finally:
            c.close()

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
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        with self._connection() as conn:
            rows = conn.execute(sql, [domain]).fetchall()
        return [self._row_to_entry(tuple(r)) for r in rows]
