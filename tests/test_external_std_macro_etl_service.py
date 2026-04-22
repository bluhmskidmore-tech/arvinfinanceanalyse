from __future__ import annotations

import json

import duckdb

from backend.app.repositories.external_data_migrations_extra import ensure_std_external_macro_schema
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService


def _entry(sid: str) -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=sid,
        series_name="X",
        vendor_name="tushare",
        source_family="tushare_macro",
        domain="macro",
        frequency="monthly",
        unit="pct",
        refresh_tier="t",
        fetch_mode="f",
        raw_zone_path="data/raw/tushare/batch/x.json",
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path="select 1",
        catalog_version="m2b.test",
        created_at="2026-04-22T00:00:00+00:00",
    )


def test_external_std_macro_etl_idempotent(tmp_path) -> None:
    raw_root = tmp_path / "data" / "raw" / "tushare" / "b1"
    raw_root.mkdir(parents=True)
    raw_file = raw_root / "m.json"
    raw_file.write_text(
        json.dumps(
            {
                "rows": [
                    {"trade_date": "2024-01-01", "value": 1.0},
                    {"trade_date": "2024-02-01", "value": 2.0},
                ],
            },
        ),
        encoding="utf-8",
    )
    db = tmp_path / "d.duckdb"
    conn = duckdb.connect(str(db))
    try:
        ensure_std_external_macro_schema(conn)
        rz = RawZoneRepository(local_raw_path=str(tmp_path / "data" / "raw"))
        etl = ExternalStdMacroEtlService(rz, conn)
        p = str(raw_file)
        e = _entry("tushare.macro.test.series")
        n1 = etl.materialize_from_raw(p, e, "batch-1")
        n2 = etl.materialize_from_raw(p, e, "batch-1")
        assert n1 == 2
        assert n2 == 2
        c = conn.execute(
            "select count(*) from std_external_macro_daily where series_id = ?",
            [e.series_id],
        ).fetchone()
        assert c is not None and c[0] == 2
    finally:
        conn.close()
