from __future__ import annotations

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
