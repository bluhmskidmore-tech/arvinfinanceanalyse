from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CacheBuildRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    job_name: str
    status: str
    cache_key: str
    cache_version: str | None = None
    lock: str
    source_version: str
    vendor_version: str
    rule_version: str | None = None

    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class CacheManifestRecord(BaseModel):
    """Governance manifest row; PnL formal jobs use ``cache_key`` ``pnl:phase2:materialize:formal``."""

    model_config = ConfigDict(extra="forbid")

    cache_key: str
    cache_version: str | None = None
    source_version: str
    vendor_version: str
    rule_version: str

    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)

    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class MaterializeBuildPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    lock: str
    cache_key: str
    run_id: str
    preview_sources: list[str]
    vendor_version: str
