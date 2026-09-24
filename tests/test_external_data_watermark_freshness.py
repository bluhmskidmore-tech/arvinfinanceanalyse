"""Watermark freshness: per-series age_days / freshness_tier + derived last_successful_ingest."""

from __future__ import annotations

from datetime import date

import duckdb

from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.external_data_migrations_extra import ensure_std_external_macro_schema
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_data_query_service import fetch_series_watermark
from backend.app.services.external_data_service import ExternalDataService


def _entry(series_id: str, frequency: str | None) -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=series_id,
        series_name=series_id,
        vendor_name="v",
        source_family="sf",
        domain="macro",
        frequency=frequency,
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        catalog_version="cv",
        created_at="2026-04-21T00:00:00+00:00",
    )


def _register(repo: ExternalDataCatalogRepository, *entries: ExternalDataCatalogEntry) -> None:
    with repository_task_write_scope("backend.app.tasks.external_data_catalog_seed_test"):
        for entry in entries:
            repo.register(entry)


def _insert_row(
    conn: duckdb.DuckDBPyConnection,
    series_id: str,
    trade_date: str,
    loaded_at: str,
) -> None:
    conn.execute(
        """
        insert or replace into std_external_macro_daily (
          series_id, vendor_name, domain, trade_date, value_numeric,
          frequency, unit, source_version, vendor_version, rule_version,
          ingest_batch_id, raw_zone_path, created_at
        ) values (?, 'v', 'macro', ?, 1.0, 'd', 'pct', 'sv', 'vv', 'rv', 'batch', null, ?)
        """,
        [series_id, trade_date, loaded_at],
    )


def _connect(tmp_path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(tmp_path / "watermark-freshness.duckdb"))
    ensure_external_data_catalog_schema(conn)
    ensure_std_external_macro_schema(conn)
    return conn


def test_fetch_series_watermark_monthly_cadence_avoids_daily_thresholds(tmp_path) -> None:
    """A 30-day-old monthly print is fresh; daily thresholds would call it expired."""
    conn = _connect(tmp_path)
    try:
        entry = _entry("s.monthly", "monthly")
        _register(ExternalDataCatalogRepository(conn=conn), entry)
        _insert_row(conn, "s.monthly", "2026-06-01", "2026-06-02 08:00:00")
        wm = fetch_series_watermark(conn, entry, as_of_date=date(2026, 7, 1))
    finally:
        conn.close()

    assert wm.age_days == 30
    assert wm.freshness_tier == "fresh"


def test_fetch_series_watermark_daily_cadence_flags_stale(tmp_path) -> None:
    conn = _connect(tmp_path)
    try:
        entry = _entry("s.daily", "daily")
        _register(ExternalDataCatalogRepository(conn=conn), entry)
        _insert_row(conn, "s.daily", "2026-06-25", "2026-06-25 18:00:00")
        wm = fetch_series_watermark(conn, entry, as_of_date=date(2026, 7, 1))
    finally:
        conn.close()

    assert wm.age_days == 6
    assert wm.freshness_tier == "stale"


def test_fetch_series_watermark_unmapped_frequency_reports_unknown_tier(tmp_path) -> None:
    """Quarterly / missing frequency must not be judged with daily thresholds."""
    conn = _connect(tmp_path)
    try:
        repo = ExternalDataCatalogRepository(conn=conn)
        quarterly = _entry("s.quarterly", "quarterly")
        nofreq = _entry("s.nofreq", None)
        _register(repo, quarterly, nofreq)
        _insert_row(conn, "s.quarterly", "2026-06-01", "2026-06-02 08:00:00")
        _insert_row(conn, "s.nofreq", "2026-06-01", "2026-06-02 08:00:00")
        wm_quarterly = fetch_series_watermark(conn, quarterly, as_of_date=date(2026, 7, 1))
        wm_nofreq = fetch_series_watermark(conn, nofreq, as_of_date=date(2026, 7, 1))
    finally:
        conn.close()

    assert wm_quarterly.age_days == 30
    assert wm_quarterly.freshness_tier == "unknown"
    assert wm_nofreq.age_days == 30
    assert wm_nofreq.freshness_tier == "unknown"


def test_fetch_series_watermark_without_rows_has_null_age_and_unknown_tier(tmp_path) -> None:
    conn = _connect(tmp_path)
    try:
        entry = _entry("s.empty", "daily")
        _register(ExternalDataCatalogRepository(conn=conn), entry)
        wm = fetch_series_watermark(conn, entry, as_of_date=date(2026, 7, 1))
    finally:
        conn.close()

    assert wm.row_count == 0
    assert wm.age_days is None
    assert wm.freshness_tier == "unknown"


def test_watermark_ledger_exposes_age_tier_and_last_successful_ingest(tmp_path) -> None:
    db_path = tmp_path / "ledger.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        _register(repo, _entry("s.monthly", "monthly"), _entry("s.nofreq", None))
        _insert_row(conn, "s.monthly", "2026-06-01", "2026-06-25 10:00:00")
        _insert_row(conn, "s.nofreq", "2026-05-20", "2026-05-21 08:00:00")
    finally:
        conn.close()

    service = ExternalDataService(
        ExternalDataCatalogRepository(path=db_path),
        duckdb_path=str(db_path),
    )
    ledger = service.get_watermark_ledger()

    assert ledger.summary.last_successful_ingest == "2026-06-25 10:00:00"

    rows = {entry.series_id: entry for entry in ledger.entries}
    # Ledger runs against date.today(): assert the derived age, and that a mapped
    # cadence yields a real tier while an unmapped one stays "unknown".
    assert rows["s.monthly"].age_days == (date.today() - date(2026, 6, 1)).days
    assert rows["s.monthly"].freshness_tier in {"fresh", "stale", "expired"}
    assert rows["s.nofreq"].age_days == (date.today() - date(2026, 5, 20)).days
    assert rows["s.nofreq"].freshness_tier == "unknown"


def test_watermark_ledger_last_successful_ingest_null_without_any_loads(tmp_path) -> None:
    db_path = tmp_path / "ledger-empty.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        _register(ExternalDataCatalogRepository(conn=conn), _entry("s.empty", "daily"))
    finally:
        conn.close()

    service = ExternalDataService(
        ExternalDataCatalogRepository(path=db_path),
        duckdb_path=str(db_path),
    )
    ledger = service.get_watermark_ledger()

    assert ledger.summary.last_successful_ingest is None
    assert ledger.entries[0].age_days is None
    assert ledger.entries[0].freshness_tier == "unknown"
