"""Catalog descriptors for official NBS monthly CPI and PPI releases."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.schemas.external_data import ExternalDataCatalogEntry

NBS_CPI_SERIES_ID = "nbs.macro.cn_cpi.monthly"
NBS_PPI_SERIES_ID = "nbs.macro.cn_ppi.monthly"
NBS_INFLATION_SERIES_IDS = (NBS_CPI_SERIES_ID, NBS_PPI_SERIES_ID)
NBS_INFLATION_SOURCE_FAMILY = "nbs_inflation_release"
NBS_INFLATION_CATALOG_VERSION = "m2b.nbs_inflation_release.v1"

_SERIES_NAMES = {
    NBS_CPI_SERIES_ID: "China CPI YoY (NBS official release)",
    NBS_PPI_SERIES_ID: "China PPI YoY (NBS official release)",
}
_RAW_FILENAMES = {
    NBS_CPI_SERIES_ID: "nbs_cn_cpi_monthly.json",
    NBS_PPI_SERIES_ID: "nbs_cn_ppi_monthly.json",
}


def nbs_inflation_raw_filename(series_id: str) -> str:
    try:
        return _RAW_FILENAMES[series_id]
    except KeyError as exc:
        raise ValueError(f"Unknown NBS inflation series: {series_id!r}") from exc


def build_nbs_inflation_catalog_entry(series_id: str) -> ExternalDataCatalogEntry:
    try:
        series_name = _SERIES_NAMES[series_id]
    except KeyError as exc:
        raise ValueError(f"Unknown NBS inflation series: {series_id!r}") from exc
    filename = nbs_inflation_raw_filename(series_id)
    return ExternalDataCatalogEntry(
        series_id=series_id,
        series_name=series_name,
        vendor_name="nbs",
        source_family=NBS_INFLATION_SOURCE_FAMILY,
        domain="macro",
        frequency="monthly",
        unit="pct",
        refresh_tier="on_demand",
        fetch_mode="live",
        raw_zone_path=f"data/raw/nbs/{{ingest_batch_id}}/{filename}",
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path=(
            "select * from vw_external_macro_daily "
            f"where series_id = '{series_id}'"
        ),
        catalog_version=NBS_INFLATION_CATALOG_VERSION,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
