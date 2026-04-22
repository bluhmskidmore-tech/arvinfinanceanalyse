"""M2a TushareMacroIngestService: raw zone + catalog + manifest (mock adapter)."""

from __future__ import annotations

from pathlib import Path

import duckdb
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.repositories.tushare_catalog_seed import TUSHARE_M2A_SERIES
from backend.app.services.tushare_macro_ingest_service import TushareMacroIngestService


class _StubAdapter(VendorAdapter):
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        super().__init__()
        self._payloads = payloads

    def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:  # type: ignore[override]
        if series_id not in self._payloads:
            raise ValueError(series_id)
        return self._payloads[series_id]


def _memory_catalog() -> ExternalDataCatalogRepository:
    conn = duckdb.connect(":memory:")
    ensure_external_data_catalog_schema(conn)
    return ExternalDataCatalogRepository(conn=conn)


def test_ingest_series_writes_raw_catalog_manifest(tmp_path: Path) -> None:
    raw = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    catalog = _memory_catalog()
    manifest = SourceManifestRepository()
    sid = "tushare.macro.cn_cpi.monthly"
    payload = {
        "vendor_kind": "tushare_macro",
        "series_id": sid,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "rows": [{"trade_date": "2024-06-01", "value": 0.2}],
    }
    adapter = _StubAdapter({sid: payload})
    svc = TushareMacroIngestService(
        adapter=adapter,
        raw_zone_repo=raw,
        catalog_repo=catalog,
        manifest_repo=manifest,
    )
    out = svc.ingest_series(sid, "batch-a")
    raw_path = Path(str(out["raw_zone_path"]))
    assert raw_path.is_file()
    assert b"vendor_kind" in raw_path.read_bytes()
    got = catalog.get_by_series_id(sid)
    assert got is not None
    assert got.series_name == "China CPI YoY (Tushare)"
    assert "m2a placeholder" in (got.access_path or "")
    rows = manifest.load_all()
    assert len(rows) == 1
    assert rows[0]["ingest_batch_id"] == "batch-a"
    assert rows[0]["archived_path"] == str(out["raw_zone_path"])


def test_ingest_all_seed_series_covers_seed_list(tmp_path: Path) -> None:
    """Both M2a seed series are ingested sequentially in one batch."""
    raw = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    catalog = _memory_catalog()
    manifest = SourceManifestRepository()
    payloads = {
        c["series_id"]: {
            "vendor_kind": "tushare_macro",
            "series_id": c["series_id"],
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "rows": [{"trade_date": "2024-01-01", "value": 1.0}],
        }
        for c in TUSHARE_M2A_SERIES
    }
    adapter = _StubAdapter(payloads)
    svc = TushareMacroIngestService(
        adapter=adapter,
        raw_zone_repo=raw,
        catalog_repo=catalog,
        manifest_repo=manifest,
    )
    results = svc.ingest_all_seed_series("batch-multi")
    assert len(results) == len(TUSHARE_M2A_SERIES)
    ids = {r["series_id"] for r in results}
    assert ids == {c["series_id"] for c in TUSHARE_M2A_SERIES}
    assert len(manifest.load_all()) == len(TUSHARE_M2A_SERIES)
