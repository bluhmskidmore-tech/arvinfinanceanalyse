"""Unit coverage for manifest selector entrypoints used by snapshot materialization."""

from __future__ import annotations

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository


def test_select_by_dimensions_are_subsets_of_eligible_manifests(tmp_path):
    governance_dir = tmp_path / "gov"
    gov = GovernanceRepository(base_dir=governance_dir)
    repo = SourceManifestRepository(governance_repo=gov)
    z1 = {
        "source_family": "zqtz",
        "report_date": "2025-12-31",
        "source_file": "ZQTZSHOW-20251231.xls",
        "source_version": "sv1",
        "archived_path": "/archive/zqtz/file.xls",
        "status": "completed",
        "ingest_batch_id": "batch-z",
    }
    z2 = {
        **z1,
        "source_file": "ZQTZSHOW-20251231-b.xls",
        "archived_path": "/archive/zqtz/other.xls",
        "ingest_batch_id": "batch-z",
    }
    tyw_row = {
        **z1,
        "source_family": "tyw",
        "source_file": "TYW.xls",
        "archived_path": "/archive/tyw/t.xls",
        "ingest_batch_id": "batch-t",
    }
    repo.add_many([z1, z2, tyw_row])

    by_batch = repo.select_by_ingest_batch_id("batch-z")
    assert len(by_batch) == 2
    assert {str(r["archived_path"]) for r in by_batch} == {
        "/archive/zqtz/file.xls",
        "/archive/zqtz/other.xls",
    }

    z_latest = repo.select_by_source_family("zqtz")
    assert len(z_latest) == 2
    assert all(str(r["ingest_batch_id"]) == "batch-z" for r in z_latest)

    z_one_day = repo.select_by_report_date("2025-12-31", source_families=["zqtz"])
    assert len(z_one_day) == 2

    z_scoped = repo.select_by_source_family("zqtz", ingest_batch_id="batch-z")
    assert len(z_scoped) == 2
