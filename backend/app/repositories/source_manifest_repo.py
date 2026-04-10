from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.app.repositories.governance_repo import (
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)


SOURCE_MANIFEST_SCHEMA_VERSION = "phase1.manifest.v1"


@dataclass
class SourceManifestRepository:
    rows: list[dict[str, object]] = field(default_factory=list)
    governance_repo: GovernanceRepository | None = None
    stream_name: str = SOURCE_MANIFEST_STREAM

    def add_many(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        existing = self.load_all()
        latest_by_identity: dict[str, dict[str, object]] = {}
        for record in existing:
            latest_by_identity[self._source_identity(record)] = record

        created_at = datetime.now(timezone.utc).isoformat()
        persisted_rows: list[dict[str, object]] = []
        for row in rows:
            record = {
                **row,
                "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
                "created_at": created_at,
            }
            previous = latest_by_identity.get(self._source_identity(record))
            if previous is None:
                record.setdefault("status", "completed")
            else:
                record["status"] = "rerun"
                record["rerun_of_batch_id"] = previous["ingest_batch_id"]

            self.rows.append(record)
            latest_by_identity[self._source_identity(record)] = record
            persisted_rows.append(record)

        if self.governance_repo is not None and persisted_rows:
            self.governance_repo.append_many_atomic(
                [(self.stream_name, record) for record in persisted_rows]
            )

        return persisted_rows

    def load_all(self) -> list[dict[str, object]]:
        if self.governance_repo is not None:
            return self.governance_repo.read_all(self.stream_name)
        return list(self.rows)

    def load_by_batch(self, ingest_batch_id: str) -> list[dict[str, object]]:
        return [
            row
            for row in self.load_all()
            if str(row.get("ingest_batch_id", "")) == ingest_batch_id
        ]

    def latest_summary(self) -> dict[str, object]:
        rows = self.load_all()
        return {
            "row_count": len(rows),
            "last_row": rows[-1] if rows else None,
        }

    @staticmethod
    def _source_identity(record: dict[str, object]) -> str:
        return "|".join(
            [
                str(record.get("source_family", "")),
                str(record.get("report_date", "")),
                str(record.get("source_file", record.get("file_name", ""))),
                str(record.get("source_version", "")),
            ]
        )
