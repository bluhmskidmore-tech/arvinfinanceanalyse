from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FormalComputeMaterializeFailure(RuntimeError):
    def __init__(
        self,
        *,
        source_version: str,
        message: str,
        vendor_version: str = "vv_none",
    ) -> None:
        super().__init__(message)
        self.source_version = source_version
        self.vendor_version = vendor_version


class FormalComputeMaterializeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version: str
    vendor_version: str = "vv_none"
    payload: dict[str, object] = Field(default_factory=dict)


class FormalComputeRuntimeRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    job_name: str
    report_date: str
    status: Literal["queued", "running", "completed", "failed"]
    lock: str
    queued_at: str
    started_at: str
    finished_at: str | None = None


class FormalComputeRuntimeLineagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cache_key: str
    cache_version: str
    source_version: str
    vendor_version: str
    rule_version: str
    basis: str
    module_name: str
    result_kind_family: str
    run_id: str
    report_date: str
    input_sources: list[str]
    fact_tables: list[str]


class FormalComputeRuntimePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: FormalComputeRuntimeRunPayload
    lineage: FormalComputeRuntimeLineagePayload
    error: dict[str, object] | None = None
    result: dict[str, object] = Field(default_factory=dict)
