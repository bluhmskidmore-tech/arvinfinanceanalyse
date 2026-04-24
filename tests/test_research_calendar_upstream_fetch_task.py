from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import pytest
from backend.app.tasks.research_calendar_upstream_fetch import _fetch_research_calendar_upstream_once


@dataclass
class _StubSettings:
    duckdb_path: str
    governance_path: str


def test_fetch_research_calendar_upstream_once_fetches_archives_and_materializes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "research-calendar-upstream.duckdb"
    gov = tmp_path / "gov"
    gov.mkdir()

    def _get_settings() -> _StubSettings:
        return _StubSettings(duckdb_path=str(db), governance_path=str(gov))

    monkeypatch.setattr("backend.app.tasks.research_calendar_upstream_fetch.get_settings", _get_settings)
    monkeypatch.setattr(
        "backend.app.tasks.research_calendar_upstream_fetch.archive_research_calendar_supply_auction_raw",
        lambda raw_zone_repo, ingest_batch_id, page_count=2, max_items=20: {
            "raw_zone_path": str(
                Path(raw_zone_repo.local_raw_path)
                / "research_calendar"
                / ingest_batch_id
                / "supply_auction_calendar.json"
            ),
            "row_count": 1,
            "payload": {
                "rows": [
                    {
                        "event_id": "evt-1",
                        "event_date": "2026-01-19",
                        "event_kind": "supply",
                        "title": "关于2026年记账式附息（三期）国债发行工作有关事宜的通知",
                        "severity": "high",
                    }
                ]
            },
        },
    )

    raw_path = tmp_path / "raw" / "research_calendar" / "batch-upstream" / "supply_auction_calendar.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "event_id": "evt-1",
                        "event_date": "2026-01-19",
                        "event_kind": "supply",
                        "title": "关于2026年记账式附息（三期）国债发行工作有关事宜的通知",
                        "severity": "high",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "backend.app.tasks.research_calendar_upstream_fetch.RawZoneRepository",
        lambda: __import__(
            "backend.app.repositories.raw_zone_repo",
            fromlist=["RawZoneRepository"],
        ).RawZoneRepository(local_raw_path=str(tmp_path / "raw")),
    )

    out = _fetch_research_calendar_upstream_once("batch-upstream")

    assert out["ingest_batch_id"] == "batch-upstream"
    assert out["fetched_rows"] == 1
    assert len(out["results"]) == 1
    assert (gov / "source_manifest.jsonl").is_file()
