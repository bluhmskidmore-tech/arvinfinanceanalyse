from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository


class ResearchCalendarSeriesConfig(TypedDict):
    series_id: str
    series_name: str
    frequency: str
    raw_zone_path_template: str


RESEARCH_CALENDAR_V1_SERIES: list[ResearchCalendarSeriesConfig] = [
    {
        "series_id": "research.calendar.supply_auction",
        "series_name": "Supply / auction research calendar (v1)",
        "frequency": "event",
        "raw_zone_path_template": "data/raw/research_calendar/{ingest_batch_id}/supply_auction_calendar.json",
    }
]

CATALOG_VERSION_V1 = "v1.research_calendar"


def register_research_calendar_v1_catalog_descriptors(
    repo: ExternalDataCatalogRepository,
) -> int:
    from backend.app.schemas.external_data import ExternalDataCatalogEntry  # noqa: PLC0415

    count = 0
    for cfg in RESEARCH_CALENDAR_V1_SERIES:
        entry = ExternalDataCatalogEntry(
            series_id=cfg["series_id"],
            series_name=cfg["series_name"],
            vendor_name="research_calendar",
            source_family="research_calendar",
            domain="other",
            frequency=cfg["frequency"],
            unit=None,
            refresh_tier="on_demand",
            fetch_mode="view_only",
            raw_zone_path=cfg["raw_zone_path_template"],
            standardized_table="std_external_supply_auction_calendar",
            view_name="vw_external_supply_auction_calendar",
            access_path=(
                "select * from vw_external_supply_auction_calendar "
                "where series_id = 'research.calendar.supply_auction'"
            ),
            catalog_version=CATALOG_VERSION_V1,
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        repo.register(entry)
        count += 1
    return count
