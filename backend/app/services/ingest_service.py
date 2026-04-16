from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.schemas.ingest import IngestManifestRow, IngestRunSummary
from backend.app.services.source_rules import describe_source_file


@dataclass
class IngestService:
    data_root: Path
    manifest_repo: SourceManifestRepository | None = None
    object_store_repo: ObjectStoreRepository | None = None
    source_family_allowlist: set[str] | None = None

    def scan(self, ingest_batch_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for path in sorted(self.data_root.rglob("*")):
            if not path.is_file():
                continue

            metadata = describe_source_file(path.name)
            source_family = metadata.source_family
            if self.source_family_allowlist is not None and source_family not in self.source_family_allowlist:
                continue

            source_name = path.name.split("-")[0] if "-" in path.name else path.parent.name
            rows.append(
                {
                    "source_name": source_name,
                    "source_family": source_family,
                    "source_file": path.name,
                    "file_name": path.name,
                    "file_path": str(path),
                    "file_size": path.stat().st_size,
                    "report_date": metadata.report_date,
                    "report_start_date": metadata.report_start_date,
                    "report_end_date": metadata.report_end_date,
                    "report_granularity": metadata.report_granularity,
                    "source_version": _build_source_version(path),
                    "ingest_batch_id": ingest_batch_id,
                }
            )

        return rows

    def scan_and_archive(self) -> list[dict[str, object]]:
        rows = self.scan()
        if self.manifest_repo is not None:
            rows = self.manifest_repo.filter_incremental_rows(rows)
        if not rows:
            return []

        ingest_batch_id = f"ib_{uuid4().hex[:12]}"
        rows = [{**row, "ingest_batch_id": ingest_batch_id} for row in rows]
        if self.object_store_repo is None:
            return rows

        archived_rows: list[dict[str, object]] = []
        for row in rows:
            source_path = Path(row["file_path"])
            source_key = source_path.relative_to(self.data_root).as_posix()
            archive_info = self.object_store_repo.archive_file(
                source_path,
                source_name=str(row["source_name"]),
                source_key=source_key,
                ingest_batch_id=ingest_batch_id,
            )
            merged = {
                **row,
                "archive_mode": archive_info["mode"],
                "archived_path": archive_info["archived_path"],
            }
            archived_rows.append(merged)

        if self.manifest_repo is not None:
            archived_rows = self.manifest_repo.add_many(archived_rows)

        return archived_rows

    def run(self) -> IngestRunSummary:
        rows = self.scan_and_archive()
        archive_mode = rows[0].get("archive_mode") if rows else None
        ingest_batch_id = rows[0].get("ingest_batch_id") if rows else None
        return IngestRunSummary(
            status="completed",
            row_count=len(rows),
            ingest_batch_id=ingest_batch_id,
            archive_mode=archive_mode,
            manifest_rows=[IngestManifestRow(**row) for row in rows],
        )


def _build_source_version(path: Path) -> str:
    stat = path.stat()
    seed = f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"
    return f"sv_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"
