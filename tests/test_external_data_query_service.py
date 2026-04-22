from __future__ import annotations

import duckdb

from backend.app.repositories.external_data_migrations_extra import ensure_std_external_macro_schema
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_data_query_service import (
    fetch_series_data_page,
    fetch_series_data_recent,
)


def _tushare_entry() -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id="s.test",
        series_name="T",
        vendor_name="tushare",
        source_family="tushare_macro",
        domain="macro",
        frequency="d",
        unit="u",
        refresh_tier="r",
        fetch_mode="f",
        raw_zone_path=None,
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path="select 1",
        catalog_version="cv",
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_query_tushare_style_filters_series() -> None:
    conn = duckdb.connect(":memory:")
    try:
        ensure_std_external_macro_schema(conn)
        conn.execute(
            """
            insert or replace into std_external_macro_daily (
              series_id, vendor_name, domain, trade_date, value_numeric,
              frequency, unit, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_zone_path, created_at
            ) values
            ('s.test', 'tushare', 'macro', '2026-01-01', 1.0, 'd', 'u', 's', 'v', 'r', 'b', null, '2026-01-01T00:00:00'),
            ('other', 'tushare', 'macro', '2026-01-02', 2.0, 'd', 'u', 's', 'v', 'r', 'b', null, '2026-01-01T00:00:00')
            """,
        )
        ent = _tushare_entry()
        p = fetch_series_data_page(conn, ent, limit=10, offset=0)
        assert p.table_name == "vw_external_macro_daily"
        assert len(p.rows) == 1
        assert p.rows[0].get("series_id") == "s.test"
        r = fetch_series_data_recent(conn, ent, days=4000, limit=10)
        assert len(r.rows) == 1
    finally:
        conn.close()
