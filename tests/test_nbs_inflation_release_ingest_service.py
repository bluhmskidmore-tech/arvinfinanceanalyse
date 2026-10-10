from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.external_data_migrations_extra import (
    ensure_std_external_macro_schema,
)
from backend.app.repositories.nbs_inflation_catalog_seed import (
    NBS_CPI_SERIES_ID,
    NBS_PPI_SERIES_ID,
)
from backend.app.repositories.nbs_inflation_release_adapter import (
    NbsInflationReleaseDocument,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService
from backend.app.services.nbs_inflation_release_ingest_service import (
    NbsInflationReleaseIngestService,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]


class _Adapter:
    vendor_name = "nbs"

    def discover_and_fetch(self, *, reference_date, reference_month, before_parse):
        assert reference_date == date(2026, 9, 16)
        assert reference_month is None
        documents = []
        values = {
            (NBS_CPI_SERIES_ID, "2026-07"): 0.5,
            (NBS_CPI_SERIES_ID, "2026-08"): 0.8,
            (NBS_PPI_SERIES_ID, "2026-07"): 3.5,
            (NBS_PPI_SERIES_ID, "2026-08"): 3.8,
        }
        for (series_id, month), value in values.items():
            slug = "cpi" if series_id == NBS_CPI_SERIES_ID else "ppi"
            compact_month = month.replace("-", "")
            release_url = (
                f"https://www.stats.gov.cn/sj/zxfb/{compact_month}/"
                f"t{compact_month}09_{slug}.html"
            )
            html_bytes = f"{series_id}:{month}:{value}".encode()
            source_version = (
                "nbs_inflation_release_sha256_"
                f"{hashlib.sha256(html_bytes).hexdigest()}"
            )
            before_parse(series_id, release_url, html_bytes)
            documents.append(
                NbsInflationReleaseDocument(
                    series_id=series_id,
                    reference_month=month,
                    release_url=release_url,
                    fetched_at=datetime(2026, 9, 16, tzinfo=UTC),
                    html_bytes=html_bytes,
                    observation={
                        "trade_date": f"{month}-01",
                        "value": value,
                        "source_version": source_version,
                    },
                )
            )
        return documents


def test_ingest_materializes_two_official_periods_per_metric(tmp_path: Path) -> None:
    conn = duckdb.connect(str(tmp_path / "nbs-inflation.duckdb"))
    manifest = SourceManifestRepository()
    raw_zone = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    try:
        ensure_external_data_catalog_schema(conn)
        ensure_std_external_macro_schema(conn)
        catalog = ExternalDataCatalogRepository(conn=conn)
        service = NbsInflationReleaseIngestService(
            adapter=_Adapter(),
            raw_zone_repo=raw_zone,
            catalog_repo=catalog,
            manifest_repo=manifest,
            etl_service=ExternalStdMacroEtlService(raw_zone, conn),
        )

        with repository_task_write_scope(
            "backend.app.tasks.nbs_inflation_release_ingest_test"
        ):
            result = service.ingest_release_month(
                "nbs-inflation-batch",
                reference_date=date(2026, 9, 16),
            )

        assert result["status"] == "success"
        assert result["reference_months"] == ["2026-07", "2026-08"]
        assert result["materialized_rows"] == 4
        assert {item["materialized_rows"] for item in result["results"]} == {2}
        rows = conn.execute(
            """
            select series_id, trade_date, value_numeric, vendor_name, unit
            from std_external_macro_daily
            order by series_id, trade_date
            """
        ).fetchall()
        assert rows == [
            (NBS_CPI_SERIES_ID, "2026-07-01", 0.5, "nbs", "pct"),
            (NBS_CPI_SERIES_ID, "2026-08-01", 0.8, "nbs", "pct"),
            (NBS_PPI_SERIES_ID, "2026-07-01", 3.5, "nbs", "pct"),
            (NBS_PPI_SERIES_ID, "2026-08-01", 3.8, "nbs", "pct"),
        ]
        for series_id in (NBS_CPI_SERIES_ID, NBS_PPI_SERIES_ID):
            entry = catalog.get_by_series_id(series_id)
            assert entry is not None
            assert entry.source_family == "nbs_inflation_release"
            result_item = next(item for item in result["results"] if item["series_id"] == series_id)
            normalized = json.loads(
                Path(str(result_item["normalized_raw_zone_path"])).read_text(encoding="utf-8")
            )
            assert len(normalized["rows"]) == 2
            assert all(row["source_version"].startswith("nbs_inflation_release_sha256_") for row in normalized["rows"])
        receipts = manifest.load_by_batch("nbs-inflation-batch")
        assert len(receipts) == 4
        assert {receipt["report_date"] for receipt in receipts} == {
            "2026-07-01",
            "2026-08-01",
        }
    finally:
        conn.close()
