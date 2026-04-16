from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VendorSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str
    vendor_version: str
    mode: Literal["skeleton"] = "skeleton"
    snapshot_kind: Literal["macro"] = "macro"
    read_target: Literal["duckdb"] = "duckdb"
    record_count: int = 0


class VendorPreflightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str
    ok: bool
    status: Literal["missing_config", "config_present"] = "missing_config"
    mode: Literal["skeleton"] = "skeleton"
    supports_live_fetch: bool = False
    detail: str | None = None


class VendorFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str
    stage: str
    message: str
    retryable: bool = False
    mode: Literal["skeleton"] = "skeleton"


class VendorSnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str
    vendor_version: str
    snapshot_kind: str
    archive_mode: str
    archived_path: str
    capture_mode: Literal["skeleton", "live"] = "skeleton"
    read_target: Literal["duckdb"] = "duckdb"


class VendorAdapter(ABC):
    vendor_name: str

    @abstractmethod
    def preflight(self) -> VendorPreflightResult:
        raise NotImplementedError

    @abstractmethod
    def fetch_snapshot(self) -> VendorSnapshot:
        raise NotImplementedError
