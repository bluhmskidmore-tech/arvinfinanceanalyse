"""Tushare macro ingest retry + failure aggregation (stub adapters, no network)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pytest

import backend.app.services.tushare_macro_ingest_service as ingest_service_module
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.repositories.tushare_catalog_seed import TUSHARE_M2A_SERIES
from backend.app.services.tushare_macro_ingest_service import TushareMacroIngestService
from backend.app.tasks.tushare_macro_ingest import run_tushare_macro_ingest_once


def _payload(series_id: str) -> dict[str, object]:
    return {
        "vendor_kind": "tushare_macro",
        "series_id": series_id,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "rows": [{"trade_date": "2024-01-01", "value": 1.0}],
    }


class _FlakyAdapter(VendorAdapter):
    """Fails ``fail_times[series_id]`` fetches for a series before succeeding."""

    def __init__(self, fail_times: dict[str, int] | None = None) -> None:
        super().__init__()
        self._remaining = dict(fail_times or {})
        self.calls: list[str] = []

    def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:  # type: ignore[override]
        self.calls.append(series_id)
        remaining = self._remaining.get(series_id, 0)
        if remaining > 0:
            self._remaining[series_id] = remaining - 1
            raise ConnectionError(f"simulated vendor outage: {series_id}")
        return _payload(series_id)


def _service(
    tmp_path: Path, adapter: VendorAdapter
) -> tuple[TushareMacroIngestService, SourceManifestRepository]:
    conn = duckdb.connect(":memory:")
    ensure_external_data_catalog_schema(conn)
    manifest = SourceManifestRepository()
    svc = TushareMacroIngestService(
        adapter=adapter,
        raw_zone_repo=RawZoneRepository(local_raw_path=str(tmp_path / "raw")),
        catalog_repo=ExternalDataCatalogRepository(conn=conn),
        manifest_repo=manifest,
    )
    return svc, manifest


def test_retry_recovers_transient_series_failure(tmp_path: Path) -> None:
    """Two transient failures on one series are absorbed by bounded retries."""
    flaky_id = TUSHARE_M2A_SERIES[0]["series_id"]
    adapter = _FlakyAdapter({flaky_id: 2})
    svc, manifest = _service(tmp_path, adapter)

    summary = svc.ingest_all_seed_series_with_summary("batch-retry", retry_sleep_seconds=0)
    assert summary["status"] == "success"

    assert summary["failed"] == []
    assert summary["succeeded"] == [c["series_id"] for c in TUSHARE_M2A_SERIES]
    assert len(summary["results"]) == len(TUSHARE_M2A_SERIES)
    assert adapter.calls.count(flaky_id) == 3  # 1 attempt + 2 retries
    assert len(manifest.load_all()) == len(TUSHARE_M2A_SERIES)


def test_persistent_failure_is_aggregated_without_aborting_batch(tmp_path: Path) -> None:
    dead_id = TUSHARE_M2A_SERIES[1]["series_id"]
    adapter = _FlakyAdapter({dead_id: 99})
    svc, manifest = _service(tmp_path, adapter)

    summary = svc.ingest_all_seed_series_with_summary("batch-dead", retry_sleep_seconds=0)
    assert summary["status"] == "partial"

    assert [f["series_id"] for f in summary["failed"]] == [dead_id]
    assert "ConnectionError" in summary["failed"][0]["error"]
    assert dead_id not in summary["succeeded"]
    assert len(summary["results"]) == len(TUSHARE_M2A_SERIES) - 1
    assert adapter.calls.count(dead_id) == 3  # retries are bounded, batch moves on
    assert len(manifest.load_all()) == len(TUSHARE_M2A_SERIES) - 1


@dataclass
class _StubSettings:
    duckdb_path: str
    governance_path: str


def _patch_task_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adapter_cls: type[VendorAdapter],
) -> None:
    db = tmp_path / "task.duckdb"
    gov = tmp_path / "gov"
    gov.mkdir(exist_ok=True)
    task_globals = run_tushare_macro_ingest_once.__globals__
    monkeypatch.setitem(
        task_globals,
        "get_settings",
        lambda: _StubSettings(duckdb_path=str(db), governance_path=str(gov)),
    )
    monkeypatch.setitem(
        task_globals,
        "RawZoneRepository",
        lambda: RawZoneRepository(local_raw_path=str(tmp_path / "raw")),
    )
    monkeypatch.setitem(task_globals, "VendorAdapter", adapter_cls)
    monkeypatch.setattr(ingest_service_module.time, "sleep", lambda _s: None)


def test_task_partial_failure_logs_error_and_reports_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    dead_id = TUSHARE_M2A_SERIES[0]["series_id"]

    class _PartialFailAdapter(VendorAdapter):
        def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:  # type: ignore[override]
            if series_id == dead_id:
                raise ConnectionError(f"vendor down: {series_id}")
            return _payload(series_id)

    _patch_task_env(tmp_path, monkeypatch, _PartialFailAdapter)

    with caplog.at_level(logging.ERROR, logger="backend.app.tasks.tushare_macro_ingest"):
        out = run_tushare_macro_ingest_once("batch-partial")

    assert out["status"] == "partial"
    assert all(result["materialized_rows"] == 1 for result in out["results"])
    assert [f["series_id"] for f in out["failed"]] == [dead_id]
    assert {r["series_id"] for r in out["results"]} == {
        c["series_id"] for c in TUSHARE_M2A_SERIES if c["series_id"] != dead_id
    }
    assert out["succeeded"] == [
        c["series_id"] for c in TUSHARE_M2A_SERIES if c["series_id"] != dead_id
    ]
    assert any("tushare macro ingest failures" in r.getMessage() for r in caplog.records)


def test_task_raises_when_all_series_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class _AlwaysFailAdapter(VendorAdapter):
        def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:  # type: ignore[override]
            raise ConnectionError(f"vendor down: {series_id}")

    _patch_task_env(tmp_path, monkeypatch, _AlwaysFailAdapter)

    with caplog.at_level(logging.ERROR, logger="backend.app.tasks.tushare_macro_ingest"):
        with pytest.raises(RuntimeError, match="failed for all"):
            run_tushare_macro_ingest_once("batch-allfail")

    assert any("tushare macro ingest failures" in r.getMessage() for r in caplog.records)
