"""M2a task: run_tushare_macro_ingest_once (mocked adapter, tmp DuckDB + governance)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.repositories.tushare_catalog_seed import TUSHARE_M2A_SERIES
from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once


@dataclass
class _StubSettings:
    duckdb_path: str
    governance_path: str


def test_run_tushare_macro_ingest_once_e2e_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Batch id, result shape, and one raw artifact per seed series (adapter mocked)."""
    db = tmp_path / "x.duckdb"
    gov = tmp_path / "gov"
    gov.mkdir()

    def _get_settings() -> _StubSettings:
        return _StubSettings(duckdb_path=str(db), governance_path=str(gov))

    monkeypatch.setattr(
        "backend.app.tasks.tushare_macro_ingest.get_settings",
        _get_settings,
    )
    payload_base = {
        "vendor_kind": "tushare_macro",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "rows": [{"trade_date": "2024-01-01", "value": 0.0}],
    }

    class _ApiStub(VendorAdapter):
        def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:  # type: ignore[override]
            return {
                **payload_base,
                "series_id": series_id,
            }

    monkeypatch.setattr("backend.app.tasks.tushare_macro_ingest.VendorAdapter", _ApiStub)
    out = run_tushare_macro_ingest_once("task-batch-1")
    assert out["ingest_batch_id"] == "task-batch-1"
    results = out["results"]
    assert len(results) == len(TUSHARE_M2A_SERIES)
    for item in results:
        p = Path(str(item["raw_zone_path"]))
        assert p.is_file()
    assert (gov / "source_manifest.jsonl").is_file()


def test_run_tushare_macro_ingest_once_auto_batch_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "y.duckdb"
    gov = tmp_path / "gv"
    gov.mkdir()

    def _get_settings() -> _StubSettings:
        return _StubSettings(duckdb_path=str(db), governance_path=str(gov))

    monkeypatch.setattr("backend.app.tasks.tushare_macro_ingest.get_settings", _get_settings)

    class _ApiStub(VendorAdapter):
        def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:  # type: ignore[override]
            return {
                "vendor_kind": "tushare_macro",
                "series_id": series_id,
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "rows": [],
            }

    monkeypatch.setattr("backend.app.tasks.tushare_macro_ingest.VendorAdapter", _ApiStub)
    out = run_tushare_macro_ingest_once()
    assert str(out["ingest_batch_id"]).startswith("tushare-macro-")
    assert len(str(out["ingest_batch_id"]).split("-")[-1]) == 8
