from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SourceLinkage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingest_batch_id: str
    source_family: str
    source_file: str
    source_version: str
    archived_path: str


class SnapshotManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_run_id: str
    target_table: Literal["zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"]
    schema_version: str
    canonical_grain_version: str
    source_linkage: SourceLinkage
    rule_version: str
    produced_row_count: int
    status: Literal["completed", "failed"]


class SnapshotBuildRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    job_name: str
    status: str
    snapshot_key: str
    lock: str
    source_version: str
    vendor_version: str
