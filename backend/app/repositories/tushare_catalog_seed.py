"""Hard-coded Tushare macro series for external-data-warehouse M2a (vendor → raw → catalog)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository


class TushareM2aSeriesConfig(TypedDict):
    series_id: str
    series_name: str
    tushare_api: str
    frequency: str
    unit: str
    raw_zone_path_template: str


TUSHARE_M2A_SERIES: list[TushareM2aSeriesConfig] = [
    {
        "series_id": "tushare.macro.cn_cpi.monthly",
        "series_name": "China CPI YoY (Tushare)",
        "tushare_api": "cn_cpi",
        "frequency": "monthly",
        "unit": "pct",
        "raw_zone_path_template": "data/raw/tushare/{ingest_batch_id}/cn_cpi_monthly.json",
    },
    {
        "series_id": "tushare.macro.cn_gdp.quarterly",
        "series_name": "China GDP YoY (Tushare)",
        "tushare_api": "cn_gdp",
        "frequency": "quarterly",
        "unit": "pct",
        "raw_zone_path_template": "data/raw/tushare/{ingest_batch_id}/cn_gdp_quarterly.json",
    },
]

_SERIES_BY_ID: dict[str, TushareM2aSeriesConfig] = {c["series_id"]: c for c in TUSHARE_M2A_SERIES}


def get_m2a_series_by_id(series_id: str) -> TushareM2aSeriesConfig | None:
    return _SERIES_BY_ID.get(series_id)


CATALOG_VERSION_M2B = "m2b.tushare_macro.v1"


def _access_path_for_tushare_series(series_id: str) -> str:
    safe = str(series_id).replace("'", "''")
    return f"select * from vw_external_macro_daily where series_id = '{safe}'"


def register_tushare_m2a_catalog_descriptors(repo: ExternalDataCatalogRepository) -> int:
    """Register Tushare M2a series rows (std/vw + access_path), without raw ingest (M2b deploy seed)."""
    from backend.app.schemas.external_data import ExternalDataCatalogEntry  # noqa: PLC0415

    n = 0
    for cfg in TUSHARE_M2A_SERIES:
        e = ExternalDataCatalogEntry(
            series_id=cfg["series_id"],
            series_name=cfg["series_name"],
            vendor_name="tushare",
            source_family="tushare_macro",
            domain="macro",
            frequency=cfg["frequency"],
            unit=cfg["unit"],
            refresh_tier="on_demand",
            fetch_mode="seed_register",
            raw_zone_path=cfg["raw_zone_path_template"],
            standardized_table="std_external_macro_daily",
            view_name="vw_external_macro_daily",
            access_path=_access_path_for_tushare_series(cfg["series_id"]),
            catalog_version=CATALOG_VERSION_M2B,
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        repo.register(e)
        n += 1
    return n
