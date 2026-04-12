"""Contract tests for `ingest` and `materialize` schemas."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.schemas.ingest import IngestManifestRow, IngestRunSummary
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord, MaterializeBuildPayload


def test_ingest_manifest_row_accepts_path_and_nullable_optionals() -> None:
    p = Path("/tmp/x.csv")
    row = IngestManifestRow(
        source_name="s",
        file_name="x.csv",
        file_path=p,
        file_size=10,
        report_date=None,
        archived_path=None,
    )
    assert row.file_path == p
    assert row.report_date is None


def test_ingest_run_summary_requires_core_fields() -> None:
    row = IngestManifestRow(
        source_name="s",
        file_name="f",
        file_path=Path("a"),
        file_size=1,
    )
    summary = IngestRunSummary(status="ok", row_count=1, manifest_rows=[row])
    assert summary.status == "ok"
    assert summary.row_count == 1
    assert len(summary.manifest_rows) == 1


def test_ingest_run_summary_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        IngestRunSummary(status="ok", row_count=0)  # type: ignore[call-arg]


def test_ingest_run_summary_model_dump_nested_structure() -> None:
    row = IngestManifestRow(
        source_name="src",
        file_name="f.txt",
        file_path=Path("rel/path.txt"),
        file_size=99,
    )
    summary = IngestRunSummary(status="done", row_count=1, manifest_rows=[row])
    dumped = summary.model_dump()
    assert dumped["manifest_rows"][0]["file_name"] == "f.txt"
    assert dumped["manifest_rows"][0]["file_path"] == Path("rel/path.txt")


def test_cache_build_run_record_model_dump_excludes_none_by_default() -> None:
    rec = CacheBuildRunRecord(
        run_id="r1",
        job_name="j",
        status="ok",
        cache_key="k",
        lock="l",
        source_version="sv",
        vendor_version="vv",
        cache_version=None,
        rule_version=None,
    )
    d = rec.model_dump()
    assert "cache_version" not in d
    assert "rule_version" not in d


def test_cache_manifest_record_model_dump_excludes_none_by_default() -> None:
    rec = CacheManifestRecord(
        cache_key="k",
        source_version="sv",
        vendor_version="vv",
        rule_version="rv",
        cache_version=None,
    )
    d = rec.model_dump()
    assert "cache_version" not in d


def test_materialize_build_payload_requires_all_fields() -> None:
    p = MaterializeBuildPayload(
        status="ok",
        lock="l",
        cache_key="ck",
        run_id="rid",
        preview_sources=["a"],
        vendor_version="vv",
    )
    assert p.preview_sources == ["a"]


def test_materialize_build_payload_missing_field_raises() -> None:
    with pytest.raises(ValidationError):
        MaterializeBuildPayload(
            status="ok",
            lock="l",
            cache_key="ck",
            run_id="rid",
            vendor_version="vv",
        )  # type: ignore[call-arg]


def test_materialize_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        MaterializeBuildPayload(
            status="s",
            lock="l",
            cache_key="k",
            run_id="r",
            preview_sources=[],
            vendor_version="v",
            extra=True,  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        CacheBuildRunRecord(
            run_id="r",
            job_name="j",
            status="s",
            cache_key="k",
            lock="l",
            source_version="sv",
            vendor_version="vv",
            bonus=1,  # type: ignore[arg-type]
        )
