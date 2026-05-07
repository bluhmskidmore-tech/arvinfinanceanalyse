from pathlib import Path

from pydantic import BaseModel


class IngestManifestRow(BaseModel):
    source_name: str
    source_family: str = "unknown"
    file_name: str
    file_path: Path
    file_size: int
    report_date: str | None = None
    report_start_date: str | None = None
    report_end_date: str | None = None
    report_granularity: str | None = None
    ingest_batch_id: str | None = None
    archive_mode: str | None = None
    archived_path: Path | None = None


class IngestRunSummary(BaseModel):
    status: str
    row_count: int
    ingest_batch_id: str | None = None
    archive_mode: str | None = None
    manifest_rows: list[IngestManifestRow]
