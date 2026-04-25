from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.app.tasks.research_calendar_ingest import run_research_calendar_ingest_once


@dataclass
class _StubSettings:
    duckdb_path: str
    governance_path: str


def test_run_research_calendar_ingest_once_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "research-calendar.duckdb"
    gov = tmp_path / "gov"
    gov.mkdir()
    batch = "research-calendar-batch-1"
    raw_path = tmp_path / "raw" / "research_calendar" / batch / "supply_auction_calendar.json"
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

    def _get_settings() -> _StubSettings:
        return _StubSettings(duckdb_path=str(db), governance_path=str(gov))

    monkeypatch.setattr("backend.app.tasks.research_calendar_ingest.get_settings", _get_settings)
    monkeypatch.setattr("backend.app.tasks.research_calendar_ingest.RawZoneRepository", lambda: __import__("backend.app.repositories.raw_zone_repo", fromlist=["RawZoneRepository"]).RawZoneRepository(local_raw_path=str(tmp_path / "raw")))

    out = run_research_calendar_ingest_once(batch)

    assert out["ingest_batch_id"] == batch
    assert len(out["results"]) == 1
    assert (gov / "source_manifest.jsonl").is_file()
