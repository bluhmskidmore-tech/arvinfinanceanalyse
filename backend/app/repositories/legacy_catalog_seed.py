"""Register legacy Choice / Akshare surfaces behind ``vw_external_legacy_*`` (M2b)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry

DomainLiteral = Literal["macro", "news", "yield_curve", "fx", "other"]

CATALOG_VERSION_M2B_LEGACY = "m2b.legacy_umbrella.v1"

LEGACY_CATALOG_SEED: list[dict[str, str | None]] = [
    {
        "series_id": "legacy.choice.macro",
        "series_name": "Choice macro (legacy, via vw_external_legacy_choice_macro)",
        "vendor_name": "choice",
        "source_family": "choice_macro",
        "domain": "macro",
        "view_name": "vw_external_legacy_choice_macro",
        "standardized_table": "fact_choice_macro_daily",
        "raw_zone_path": None,
        "access_path": "select * from vw_external_legacy_choice_macro",
    },
    {
        "series_id": "legacy.choice.news",
        "series_name": "Choice news (legacy, via vw_external_legacy_choice_news)",
        "vendor_name": "choice",
        "source_family": "choice_news",
        "domain": "news",
        "view_name": "vw_external_legacy_choice_news",
        "standardized_table": None,
        "raw_zone_path": None,
        "access_path": "select * from vw_external_legacy_choice_news",
    },
    {
        "series_id": "legacy.akshare.yield_curve",
        "series_name": "Akshare yield curve (legacy, via vw_external_legacy_yield_curve)",
        "vendor_name": "akshare",
        "source_family": "akshare_yield",
        "domain": "yield_curve",
        "view_name": "vw_external_legacy_yield_curve",
        "standardized_table": "fact_formal_yield_curve_daily",
        "raw_zone_path": None,
        "access_path": "select * from vw_external_legacy_yield_curve",
    },
    {
        "series_id": "legacy.akshare.fx_mid",
        "series_name": "FX mid (legacy, via vw_external_legacy_fx_mid)",
        "vendor_name": "akshare",
        "source_family": "akshare_fx",
        "domain": "fx",
        "view_name": "vw_external_legacy_fx_mid",
        "standardized_table": "fx_daily_mid",
        "raw_zone_path": None,
        "access_path": "select * from vw_external_legacy_fx_mid",
    },
]


def register_legacy_seed(catalog_repo: ExternalDataCatalogRepository) -> int:
    """Register all legacy umbrella series; returns number of entries written."""
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    n = 0
    for item in LEGACY_CATALOG_SEED:
        e = ExternalDataCatalogEntry(
            series_id=str(item["series_id"]),
            series_name=str(item["series_name"]),
            vendor_name=str(item["vendor_name"]),
            source_family=str(item["source_family"]),
            domain=cast(DomainLiteral, str(item["domain"])),
            frequency="daily",
            unit=None,
            refresh_tier="legacy_readonly",
            fetch_mode="view_only",
            raw_zone_path=item.get("raw_zone_path") if item.get("raw_zone_path") else None,
            standardized_table=str(item["standardized_table"])
            if item.get("standardized_table")
            else None,
            view_name=str(item["view_name"]) if item.get("view_name") else None,
            access_path=str(item["access_path"]) if item.get("access_path") else None,
            catalog_version=CATALOG_VERSION_M2B_LEGACY,
            created_at=now,
        )
        catalog_repo.register(e)
        n += 1
    return n
