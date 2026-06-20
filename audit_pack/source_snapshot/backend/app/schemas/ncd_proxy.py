from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NcdFundingProxyRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    row_key: str
    label: str
    tenor_1m: float | None = Field(default=None, alias="1M")
    tenor_3m: float | None = Field(default=None, alias="3M")
    tenor_6m: float | None = Field(default=None, alias="6M")
    tenor_9m: float | None = Field(default=None, alias="9M")
    tenor_1y: float | None = Field(default=None, alias="1Y")
    quote_count: int | None = None


class NcdFundingProxyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: str | None = None
    proxy_label: str
    is_actual_ncd_matrix: bool = False
    rows: list[NcdFundingProxyRow]
    warnings: list[str] = []
