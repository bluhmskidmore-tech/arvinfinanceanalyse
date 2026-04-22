"""Hard-coded Tushare macro series for external-data-warehouse M2a (vendor → raw → catalog)."""

from __future__ import annotations

from typing import TypedDict


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
