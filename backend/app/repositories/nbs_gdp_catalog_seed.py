"""Governed catalog descriptor for official NBS quarterly GDP YoY."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.schemas.external_data import ExternalDataCatalogEntry

NBS_GDP_SERIES_ID = "nbs.macro.cn_gdp.quarterly"
NBS_GDP_SOURCE_FAMILY = "nbs_gdp_release"
NBS_GDP_CATALOG_VERSION = "m2b.nbs_gdp_release.v1"
NBS_GDP_RAW_PATH_TEMPLATE = "data/raw/nbs/{ingest_batch_id}/nbs_gdp_quarterly.json"


def build_nbs_gdp_catalog_entry() -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=NBS_GDP_SERIES_ID,
        series_name="China GDP YoY (NBS official release)",
        vendor_name="nbs",
        source_family=NBS_GDP_SOURCE_FAMILY,
        domain="macro",
        frequency="quarterly",
        unit="pct",
        refresh_tier="on_demand",
        fetch_mode="live",
        raw_zone_path=NBS_GDP_RAW_PATH_TEMPLATE,
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path=(
            "select * from vw_external_macro_daily "
            f"where series_id = '{NBS_GDP_SERIES_ID}'"
        ),
        catalog_version=NBS_GDP_CATALOG_VERSION,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
