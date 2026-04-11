from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CacheBuildRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    job_name: str
    status: str
    cache_key: str
    lock: str
    source_version: str
    vendor_version: str
    rule_version: str | None = None


class CacheManifestRecord(BaseModel):
    """Governance manifest row; PnL formal jobs use ``cache_key`` ``pnl:phase2:materialize:formal``."""

    model_config = ConfigDict(extra="forbid")

    cache_key: str
    source_version: str
    vendor_version: str
    rule_version: str


class MaterializeBuildPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    lock: str
    cache_key: str
    run_id: str
    preview_sources: list[str]
    vendor_version: str
