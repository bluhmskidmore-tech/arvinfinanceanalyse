from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import (
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)

SOURCE_MANIFEST_SCHEMA_VERSION = "phase1.manifest.v1"
MANIFEST_ELIGIBLE_STATUSES = frozenset({"completed", "rerun"})
AUG31_SOURCE_MANIFEST_DATE = "2026-08-31"
AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY = "balance.source_manifest.selected_sha256"
_AUG31_SOURCE_FAMILIES = frozenset({"zqtz", "tyw"})


def aug31_source_manifest_lock(governance_dir: Path | str) -> LockDefinition:
    canonical_dir = Path(governance_dir).resolve()
    digest = hashlib.sha256(str(canonical_dir).encode("utf-8")).hexdigest()[:12]
    return LockDefinition(key=f"lock:balance:aug31:source-manifest:{digest}", ttl_seconds=7200)


def selected_aug31_source_manifest_hash(governance_dir: Path | str) -> str:
    repo = SourceManifestRepository(
        governance_repo=GovernanceRepository(base_dir=governance_dir)
    )
    selected: list[dict[str, object]] = []
    for family in sorted(_AUG31_SOURCE_FAMILIES):
        rows = repo.select_for_snapshot_materialization(
            source_families=[family], report_date=AUG31_SOURCE_MANIFEST_DATE
        )
        if not rows:
            raise ValueError(f"2026-08-31 {family} selected source manifest is missing.")
        selected.extend(rows)
    payload = json.dumps(
        selected, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class SourceManifestRepository:
    rows: list[dict[str, object]] = field(default_factory=list)
    governance_repo: GovernanceRepository | None = None
    stream_name: str = SOURCE_MANIFEST_STREAM

    def add_many(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        guarded = self.governance_repo is not None and any(
            str(row.get("report_date", "")) == AUG31_SOURCE_MANIFEST_DATE
            and str(row.get("source_family", "")) in _AUG31_SOURCE_FAMILIES
            for row in rows
        )
        cohort_lock = (
            acquire_lock(
                aug31_source_manifest_lock(self.governance_repo.base_dir),
                base_dir=self.governance_repo.base_dir,
            )
            if guarded and self.governance_repo is not None
            else nullcontext()
        )
        with cohort_lock:
            existing = self.load_all()
            latest_by_identity: dict[str, dict[str, object]] = {}
            for record in existing:
                latest_by_identity[self._source_identity(record)] = record

            created_at = datetime.now(UTC).isoformat()
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

                latest_by_identity[self._source_identity(record)] = record
                persisted_rows.append(record)

            if self.governance_repo is not None and persisted_rows:
                self.governance_repo.append_many_atomic(
                    [(self.stream_name, record) for record in persisted_rows]
                )
            self.rows.extend(persisted_rows)
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

    def select_by_ingest_batch_id(self, ingest_batch_id: str) -> list[dict[str, object]]:
        return self.select_for_snapshot_materialization(ingest_batch_id=ingest_batch_id)

    def select_by_source_family(
        self,
        source_family: str,
        *,
        report_date: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> list[dict[str, object]]:
        return self.select_for_snapshot_materialization(
            source_families=[source_family],
            report_date=report_date,
            ingest_batch_id=ingest_batch_id,
        )

    def select_by_report_date(
        self,
        report_date: str,
        *,
        source_families: list[str] | None = None,
        ingest_batch_id: str | None = None,
    ) -> list[dict[str, object]]:
        return self.select_for_snapshot_materialization(
            source_families=source_families,
            report_date=report_date,
            ingest_batch_id=ingest_batch_id,
        )

    def latest_summary(self) -> dict[str, object]:
        rows = self.load_all()
        return {
            "row_count": len(rows),
            "last_row": rows[-1] if rows else None,
        }

    def filter_incremental_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        latest_by_slot = self._latest_by_source_slot()
        incremental_rows: list[dict[str, object]] = []
        for row in rows:
            previous = latest_by_slot.get(self._source_slot_identity(row))
            if previous is not None and str(previous.get("source_version", "")) == str(
                row.get("source_version", "")
            ):
                continue
            incremental_rows.append(row)
        return incremental_rows

    def select_for_snapshot_materialization(
        self,
        *,
        source_families: list[str] | None = None,
        report_date: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> list[dict[str, object]]:
        rows = self.load_all()
        eligible = [
            row
            for row in rows
            if str(row.get("status", "")) in MANIFEST_ELIGIBLE_STATUSES and row.get("archived_path")
        ]
        if source_families is not None:
            allowed = set(source_families)
            eligible = [row for row in eligible if str(row.get("source_family", "")) in allowed]
        if report_date is not None:
            eligible = [row for row in eligible if str(row.get("report_date", "")) == report_date]
        if ingest_batch_id is not None:
            scoped = [
                row for row in eligible if str(row.get("ingest_batch_id", "")) == ingest_batch_id
            ]
            return sorted(scoped, key=lambda item: str(item.get("archived_path", "")))

        latest_rows: list[dict[str, object]] = []
        families = sorted({str(row.get("source_family", "")) for row in eligible if row.get("source_family")})
        if source_families is not None:
            families = [family for family in families if family in set(source_families)]
        for family in families:
            family_rows = [row for row in eligible if str(row.get("source_family", "")) == family]
            if not family_rows:
                continue
            if report_date is None:
                latest_report = max(str(row.get("report_date", "")) for row in family_rows)
            else:
                latest_report = report_date
            bounded = [row for row in family_rows if str(row.get("report_date", "")) == latest_report]
            if not bounded:
                continue
            latest_batch_id = max(bounded, key=self._manifest_sort_key)["ingest_batch_id"]
            latest_rows.extend(
                sorted(
                    [
                        row
                        for row in bounded
                        if str(row.get("ingest_batch_id", "")) == str(latest_batch_id)
                    ],
                    key=lambda item: str(item.get("archived_path", "")),
                )
            )
        return latest_rows

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

    @staticmethod
    def _source_slot_identity(record: dict[str, object]) -> str:
        return "|".join(
            [
                str(record.get("source_family", "")),
                str(record.get("report_date", "")),
                str(record.get("source_file", record.get("file_name", ""))),
            ]
        )

    def _latest_by_source_slot(self) -> dict[str, dict[str, object]]:
        latest: dict[str, dict[str, object]] = {}
        for record in self.load_all():
            if str(record.get("status", "")) not in MANIFEST_ELIGIBLE_STATUSES:
                continue
            slot = self._source_slot_identity(record)
            current = latest.get(slot)
            if current is None or self._manifest_sort_key(record) >= self._manifest_sort_key(current):
                latest[slot] = record
        return latest

    @staticmethod
    def _manifest_sort_key(record: dict[str, object]) -> tuple[str, str]:
        return (
            str(record.get("created_at", "")),
            str(record.get("ingest_batch_id", "")),
        )
