from __future__ import annotations

import json

import duckdb

from backend.app.repositories.external_data_migrations_extra import (
    ensure_std_external_macro_schema,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService


def test_external_std_macro_etl_preserves_explicit_official_versions(tmp_path) -> None:
    raw_root = tmp_path / "data" / "raw" / "nbs" / "b1"
    raw_root.mkdir(parents=True)
    raw_file = raw_root / "gdp.json"
    raw_file.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "trade_date": "2026-06-30",
                        "value": 4.3,
                        "source_version": "nbs_gdp_release_sha256_deadbeef",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    entry = ExternalDataCatalogEntry(
        series_id="nbs.macro.cn_gdp.quarterly",
        series_name="China GDP YoY (NBS official release)",
        vendor_name="nbs",
        source_family="nbs_gdp_release",
        domain="macro",
        frequency="quarterly",
        unit="pct",
        refresh_tier="on_demand",
        fetch_mode="batch_materialize",
        raw_zone_path="data/raw/nbs/b1/gdp.json",
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path="select 1",
        catalog_version="m2b.nbs_gdp_release.v1",
        created_at="2026-07-17T00:00:00+00:00",
    )
    conn = duckdb.connect(str(tmp_path / "nbs.duckdb"))
    try:
        ensure_std_external_macro_schema(conn)
        raw_zone = RawZoneRepository(local_raw_path=str(tmp_path / "data" / "raw"))
        service = ExternalStdMacroEtlService(raw_zone, conn)

        count = service.materialize_from_raw(
            str(raw_file),
            entry,
            "nbs-gdp-batch-1",
            vendor_version="vv_nbs_gdp_release_sha256_deadbeef",
            rule_version="rv_nbs_gdp_release_v1",
        )

        row = conn.execute(
            """
            select vendor_name, vendor_version, source_version, rule_version
            from std_external_macro_daily
            where series_id = 'nbs.macro.cn_gdp.quarterly'
            """
        ).fetchone()
        assert count == 1
        assert row == (
            "nbs",
            "vv_nbs_gdp_release_sha256_deadbeef",
            "nbs_gdp_release_sha256_deadbeef",
            "rv_nbs_gdp_release_v1",
        )
    finally:
        conn.close()
