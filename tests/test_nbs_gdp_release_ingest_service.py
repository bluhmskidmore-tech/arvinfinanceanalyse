from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.external_data_migrations_extra import (
    ensure_std_external_macro_schema,
)
from backend.app.repositories.nbs_gdp_release_adapter import (
    NbsGdpReleaseAdapter,
    NbsGdpReleaseDocument,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService
from backend.app.services.nbs_gdp_release_ingest_service import NbsGdpReleaseIngestService


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "nbs_gdp_release"
LISTING_HTML = (FIXTURE_ROOT / "listing.html").read_bytes()
RELEASE_HTML = (FIXTURE_ROOT / "2026_h1_release.html").read_bytes()
RELEASE_URL = "https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html"


class _Response:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}


def _adapter(tmp_path: Path, release_html: bytes = RELEASE_HTML) -> NbsGdpReleaseAdapter:
    responses = [
        _Response(LISTING_HTML, "https://www.stats.gov.cn/sj/xwfbh/fbhwd/"),
        _Response(release_html, RELEASE_URL),
    ]

    def fake_get(*_: Any, **__: Any) -> _Response:
        return responses.pop(0)

    config = json.loads((ROOT / "config" / "nbs_gdp_release_source.json").read_text())
    config_path = tmp_path / f"source-{hashlib.sha256(release_html).hexdigest()[:8]}.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return NbsGdpReleaseAdapter(config_path=config_path, get=fake_get)


def _service(
    tmp_path: Path,
    conn: duckdb.DuckDBPyConnection,
    adapter: Any,
    manifest: SourceManifestRepository,
) -> tuple[NbsGdpReleaseIngestService, RawZoneRepository, ExternalDataCatalogRepository]:
    raw_zone = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    catalog = ExternalDataCatalogRepository(conn=conn)
    service = NbsGdpReleaseIngestService(
        adapter=adapter,
        raw_zone_repo=raw_zone,
        catalog_repo=catalog,
        manifest_repo=manifest,
        etl_service=ExternalStdMacroEtlService(raw_zone, conn),
    )
    return service, raw_zone, catalog


def test_ingest_archives_official_html_and_materializes_governed_rows(tmp_path: Path) -> None:
    conn = duckdb.connect(str(tmp_path / "nbs.duckdb"))
    manifest = SourceManifestRepository()
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        service, _, catalog = _service(tmp_path, conn, _adapter(tmp_path), manifest)

        result = service.ingest_release("nbs-gdp-batch-1", reference_date=date(2026, 7, 17))

        digest = hashlib.sha256(RELEASE_HTML).hexdigest()
        assert result == {
            "status": "success",
            "series_id": "nbs.macro.cn_gdp.quarterly",
            "release_url": RELEASE_URL,
            "latest_observation": "2026-06-30",
            "materialized_rows": 2,
            "source_version": f"nbs_gdp_release_sha256_{digest}",
            "vendor_version": f"vv_nbs_gdp_release_sha256_{digest}",
            "rule_version": "rv_nbs_gdp_release_v1",
            "html_raw_zone_path": result["html_raw_zone_path"],
            "normalized_raw_zone_path": result["normalized_raw_zone_path"],
        }
        assert Path(str(result["html_raw_zone_path"])).read_bytes() == RELEASE_HTML
        normalized = json.loads(Path(str(result["normalized_raw_zone_path"])).read_text())
        assert [row["value"] for row in normalized["rows"]] == [5.0, 4.3]
        assert normalized["release_url"] == RELEASE_URL

        entry = catalog.get_by_series_id("nbs.macro.cn_gdp.quarterly")
        assert entry is not None
        assert (entry.vendor_name, entry.source_family, entry.frequency, entry.unit) == (
            "nbs",
            "nbs_gdp_release",
            "quarterly",
            "pct",
        )
        rows = conn.execute(
            """
            select trade_date, value_numeric, vendor_name, vendor_version,
                   source_version, rule_version
            from std_external_macro_daily
            where series_id = 'nbs.macro.cn_gdp.quarterly'
            order by trade_date
            """
        ).fetchall()
        assert rows == [
            (
                "2026-03-31",
                5.0,
                "nbs",
                f"vv_nbs_gdp_release_sha256_{digest}",
                f"nbs_gdp_release_sha256_{digest}",
                "rv_nbs_gdp_release_v1",
            ),
            (
                "2026-06-30",
                4.3,
                "nbs",
                f"vv_nbs_gdp_release_sha256_{digest}",
                f"nbs_gdp_release_sha256_{digest}",
                "rv_nbs_gdp_release_v1",
            ),
        ]
        receipt = manifest.load_by_batch("nbs-gdp-batch-1")[0]
        assert receipt["release_url"] == RELEASE_URL
        assert receipt["html_archive_path"] == result["html_raw_zone_path"]
        assert receipt["normalized_archive_path"] == result["normalized_raw_zone_path"]
        assert receipt["report_date"] == "2026-06-30"
        assert receipt["content_sha256"] == digest
    finally:
        conn.close()


def test_identical_rerun_is_idempotent_and_records_rerun_lineage(tmp_path: Path) -> None:
    conn = duckdb.connect(str(tmp_path / "rerun.duckdb"))
    manifest = SourceManifestRepository()
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        first, _, _ = _service(tmp_path, conn, _adapter(tmp_path), manifest)
        second, _, _ = _service(tmp_path, conn, _adapter(tmp_path), manifest)

        first.ingest_release("same-batch", reference_date=date(2026, 7, 17))
        second.ingest_release("same-batch", reference_date=date(2026, 7, 17))

        count = conn.execute(
            """
            select count(*) from std_external_macro_daily
            where series_id = 'nbs.macro.cn_gdp.quarterly'
            """
        ).fetchone()
        assert count == (2,)
        receipts = manifest.load_by_batch("same-batch")
        assert [row["status"] for row in receipts] == ["completed", "rerun"]
        assert receipts[1]["rerun_of_batch_id"] == "same-batch"
    finally:
        conn.close()


def test_invalid_observations_archive_html_but_do_not_register_success(tmp_path: Path) -> None:
    class InvalidAdapter:
        def discover_and_fetch(self, *, reference_date: date, before_parse):
            del reference_date
            before_parse(RELEASE_URL, RELEASE_HTML)
            return NbsGdpReleaseDocument(
                release_url=RELEASE_URL,
                fetched_at=datetime(2026, 7, 17, tzinfo=UTC),
                html_bytes=RELEASE_HTML,
                observations=[],
            )

    conn = duckdb.connect(str(tmp_path / "invalid.duckdb"))
    manifest = SourceManifestRepository()
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        service, _, catalog = _service(tmp_path, conn, InvalidAdapter(), manifest)

        with pytest.raises(ValueError, match="non-empty"):
            service.ingest_release("invalid-batch", reference_date=date(2026, 7, 17))

        assert catalog.get_by_series_id("nbs.macro.cn_gdp.quarterly") is None
        assert manifest.load_all() == []
        assert conn.execute("select count(*) from std_external_macro_daily").fetchone() == (0,)
        assert len(list((tmp_path / "raw" / "nbs" / "invalid-batch").glob("*.html"))) == 1
    finally:
        conn.close()


def test_conflicting_content_at_same_immutable_html_path_fails(tmp_path: Path) -> None:
    conn = duckdb.connect(str(tmp_path / "conflict.duckdb"))
    manifest = SourceManifestRepository()
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        service, raw_zone, catalog = _service(tmp_path, conn, _adapter(tmp_path), manifest)
        raw_zone.archive_bytes(
            "nbs",
            "conflict-batch",
            "nbs_gdp_release_t20260715_1964121.html",
            b"other",
        )

        with pytest.raises(FileExistsError, match="different content"):
            service.ingest_release("conflict-batch", reference_date=date(2026, 7, 17))

        assert catalog.get_by_series_id("nbs.macro.cn_gdp.quarterly") is None
        assert manifest.load_all() == []
        assert conn.execute("select count(*) from std_external_macro_daily").fetchone() == (0,)
    finally:
        conn.close()
