from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.result_meta import ResultMeta


CubeBasis = Literal["formal", "scenario", "analytical"]


class CubeQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    fact_table: str
    measures: list[str]
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, list[str]] = Field(default_factory=dict)
    order_by: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    basis: CubeBasis = "formal"

    @field_validator("fact_table")
    @classmethod
    def validate_fact_table(cls, value: str) -> str:
        allowed = {"bond_analytics", "pnl", "balance", "product_category"}
        if value not in allowed:
            raise ValueError(f"Unsupported fact_table={value}")
        return value


class DrillPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    label: str
    available_values: list[str] = Field(default_factory=list)
    current_filter: list[str] | None = None


class CubeQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    fact_table: str
    measures: list[str]
    dimensions: list[str]
    rows: list[dict[str, object]]
    total_rows: int
    drill_paths: list[DrillPath] = Field(default_factory=list)
    result_meta: ResultMeta

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_models(cls, data: Any) -> Any:
        if isinstance(data, dict):
            result_meta = data.get("result_meta")
            if hasattr(result_meta, "model_dump"):
                data = {
                    **data,
                    "result_meta": result_meta.model_dump(mode="python"),
                }
        return data
