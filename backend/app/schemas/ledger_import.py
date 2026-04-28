from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LedgerImportBatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: int
    file_name: str
    file_hash: str
    as_of_date: str
    status: str
    row_count: int
    error_count: int
    source_version: str
    rule_version: str


class LedgerImportListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: int
    filename: str
    file_hash: str
    status: str
    as_of_date: str
    row_count: int
    error_count: int
    created_at: str
    source_version: str
    rule_version: str
