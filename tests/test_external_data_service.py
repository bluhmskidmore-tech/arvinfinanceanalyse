from __future__ import annotations

from unittest.mock import MagicMock

import duckdb
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.external_data_migrations_extra import ensure_std_external_macro_schema
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_data_service import ExternalDataService


def _entry(sid: str) -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=sid,
        series_name="n",
        vendor_name="v",
        source_family="sf",
        domain="macro",
        catalog_version="cv",
        created_at="2026-04-21T00:00:00+00:00",
    )


def test_service_delegates_list_get_by_domain() -> None:
    mock_repo = MagicMock(spec=ExternalDataCatalogRepository)
    mock_repo.list_all.return_value = [_entry("a")]
    mock_repo.get_by_series_id.return_value = _entry("a")
    mock_repo.list_by_domain.return_value = [_entry("a")]

    svc = ExternalDataService(mock_repo)
    assert svc.list_catalog() == [_entry("a")]
    assert svc.get_catalog_entry("a") == _entry("a")
    assert svc.list_by_domain("macro") == [_entry("a")]

    mock_repo.list_all.assert_called_once()
    mock_repo.get_by_series_id.assert_called_once_with("a")
    mock_repo.list_by_domain.assert_called_once_with("macro")


def test_service_fetches_series_data_pages_from_configured_duckdb(tmp_path) -> None:
    db_path = tmp_path / "external-service.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        entry = ExternalDataCatalogEntry(
            series_id="s.test",
            series_name="n",
            vendor_name="v",
            source_family="sf",
            domain="macro",
            standardized_table="std_external_macro_daily",
            view_name="vw_external_macro_daily",
            catalog_version="cv",
            created_at="2026-04-21T00:00:00+00:00",
        )
        ExternalDataCatalogRepository(conn=conn).register(entry)
        conn.execute(
            """
            insert or replace into std_external_macro_daily (
              series_id, vendor_name, domain, trade_date, value_numeric,
              frequency, unit, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_zone_path, created_at
            ) values
            ('s.test', 'v', 'macro', '2026-04-20', 1.25, 'd', 'pct', 'sv', 'vv', 'rv', 'batch', null, '2026-04-21T00:00:00'),
            ('other', 'v', 'macro', '2026-04-21', 9.99, 'd', 'pct', 'sv', 'vv', 'rv', 'batch', null, '2026-04-21T00:00:00')
            """,
        )
    finally:
        conn.close()

    service = ExternalDataService(
        ExternalDataCatalogRepository(path=db_path),
        duckdb_path=str(db_path),
    )

    page = service.get_series_data_page("s.test", limit=10, offset=0)
    recent = service.get_series_data_recent("s.test", days=3650, limit=10)

    assert page is not None
    assert page.table_name == "vw_external_macro_daily"
    assert len(page.rows) == 1
    assert page.rows[0]["series_id"] == "s.test"
    assert recent is not None
    assert len(recent.rows) == 1
    assert service.get_series_data_page("missing") is None


def test_service_builds_external_data_watermark_ledger(tmp_path) -> None:
    db_path = tmp_path / "external-watermark.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        for series_id in ("s.empty", "s.test"):
            repo.register(
                ExternalDataCatalogEntry(
                    series_id=series_id,
                    series_name=series_id,
                    vendor_name="v",
                    source_family="sf",
                    domain="macro",
                    standardized_table="std_external_macro_daily",
                    view_name="vw_external_macro_daily",
                    catalog_version="cv",
                    created_at="2026-04-21T00:00:00+00:00",
                )
            )
        conn.execute(
            """
            insert or replace into std_external_macro_daily (
              series_id, vendor_name, domain, trade_date, value_numeric,
              frequency, unit, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_zone_path, created_at
            ) values
            ('s.test', 'v', 'macro', '2026-04-20', 1.25, 'd', 'pct', 'sv', 'vv', 'rv', 'batch-1', null, timestamp '2026-04-21 08:00:00'),
            ('s.test', 'v', 'macro', '2026-04-22', 1.30, 'd', 'pct', 'sv', 'vv', 'rv', 'batch-2', null, timestamp '2026-04-23 09:00:00'),
            ('other', 'v', 'macro', '2026-04-24', 9.99, 'd', 'pct', 'sv', 'vv', 'rv', 'batch-3', null, timestamp '2026-04-25 10:00:00')
            """,
        )
    finally:
        conn.close()

    service = ExternalDataService(
        ExternalDataCatalogRepository(path=db_path),
        duckdb_path=str(db_path),
    )

    ledger = service.get_watermark_ledger()

    assert ledger.summary.catalog_count == 2
    assert ledger.summary.available_count == 1
    assert ledger.summary.no_data_count == 1
    assert ledger.summary.unavailable_count == 0
    assert ledger.summary.oldest_available_business_date == "2026-04-22"
    assert ledger.summary.newest_available_business_date == "2026-04-22"

    rows = {entry.series_id: entry for entry in ledger.entries}
    assert rows["s.test"].data_status == "available"
    assert rows["s.test"].relation_name == "vw_external_macro_daily"
    assert rows["s.test"].date_column == "trade_date"
    assert rows["s.test"].row_count == 2
    assert rows["s.test"].latest_business_date == "2026-04-22"
    assert rows["s.test"].latest_loaded_at == "2026-04-23 09:00:00"

    assert rows["s.empty"].data_status == "no_data"
    assert rows["s.empty"].row_count == 0
    assert rows["s.empty"].latest_business_date is None
