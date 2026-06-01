from __future__ import annotations

import json
from pathlib import Path

import duckdb

from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.research_calendar_repo import ensure_supply_auction_calendar_schema
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_research_calendar_etl_service import (
    ExternalStdResearchCalendarEtlService,
)
from backend.app.services.research_calendar_ingest_service import ResearchCalendarIngestService


def _memory_catalog() -> ExternalDataCatalogRepository:
    conn = duckdb.connect(":memory:")
    ensure_external_data_catalog_schema(conn)
    ensure_supply_auction_calendar_schema(conn)
    return ExternalDataCatalogRepository(conn=conn)


def test_research_calendar_ingest_materializes_rows_and_manifest(tmp_path: Path) -> None:
    raw = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    catalog = _memory_catalog()
    manifest = SourceManifestRepository()
    conn = catalog._conn
    assert conn is not None
    batch = "research-calendar-batch-a"
    raw_path = Path(raw.local_raw_path) / "research_calendar" / batch / "supply_auction_calendar.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "event_id": "evt-1",
                        "event_date": "2026-04-25",
                        "event_kind": "auction",
                        "title": "国开债 3Y 招标",
                        "severity": "high",
                        "source_family": "research_calendar",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = ResearchCalendarIngestService(
        raw_zone_repo=raw,
        catalog_repo=catalog,
        manifest_repo=manifest,
        etl_service=ExternalStdResearchCalendarEtlService(raw, conn),
    )

    result = service.materialize_all(batch)

    assert len(result) == 1
    row_count = conn.execute("select count(*) from std_external_supply_auction_calendar").fetchone()[0]
    assert row_count == 1
    entry = catalog.get_by_series_id("research.calendar.supply_auction")
    assert entry is not None
    assert entry.domain == "other"
    manifest_rows = manifest.load_all()
    assert len(manifest_rows) == 1
    assert manifest_rows[0]["ingest_batch_id"] == batch


def test_research_calendar_ingest_replaces_existing_event_rows_across_batches(tmp_path: Path) -> None:
    raw = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    catalog = _memory_catalog()
    manifest = SourceManifestRepository()
    conn = catalog._conn
    assert conn is not None
    service = ResearchCalendarIngestService(
        raw_zone_repo=raw,
        catalog_repo=catalog,
        manifest_repo=manifest,
        etl_service=ExternalStdResearchCalendarEtlService(raw, conn),
    )

    for batch, title in (
        ("research-calendar-batch-a", "第一次抓取"),
        ("research-calendar-batch-b", "第二次抓取"),
    ):
        raw_path = Path(raw.local_raw_path) / "research_calendar" / batch / "supply_auction_calendar.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "event_id": "evt-1",
                            "event_date": "2026-04-25",
                            "event_kind": "auction",
                            "title": title,
                            "severity": "high",
                            "source_family": "research_calendar",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        service.materialize_all(batch)

    std_rows = conn.execute(
        "select count(*), max(title) from std_external_supply_auction_calendar where event_id = 'evt-1'"
    ).fetchone()
    view_rows = conn.execute(
        "select count(*), max(title) from vw_external_supply_auction_calendar where event_id = 'evt-1'"
    ).fetchone()
    assert std_rows == (1, "第二次抓取")
    assert view_rows == (1, "第二次抓取")
